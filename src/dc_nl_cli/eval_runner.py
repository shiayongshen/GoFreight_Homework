from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from dc_nl_cli.config import Settings, load_settings
from dc_nl_cli.errors import DCNLError
from dc_nl_cli.llm.factory import build_llm_client
from dc_nl_cli.llm.wrappers import RateLimitedLLMClient, RateLimiter
from dc_nl_cli.pipeline import build_pipeline


DEFAULT_DATASET = Path("eval/datasets/error_cases.json")
DEFAULT_OUTPUT = Path("eval/reports/eval_report.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run evaluation over the dataset.")
    parser.add_argument(
        "--dataset", default=str(DEFAULT_DATASET), help="Path to the JSON dataset file."
    )
    parser.add_argument(
        "--resolver-mode",
        choices=["api", "hybrid", "hardrule"],
        default="api",
        help="Resolver mode used during evaluation.",
    )
    parser.add_argument(
        "--max-workers", type=int, default=8, help="Maximum concurrent workers."
    )
    parser.add_argument(
        "--max-rpm",
        type=float,
        default=None,
        help="Optional global LLM request cap in requests per minute across eval workers.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to write the full evaluation report as JSON.",
    )
    return parser.parse_args()


def load_dataset(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def make_settings(resolver_mode: str) -> Settings:
    settings = load_settings()
    return type(settings)(**{**settings.__dict__, "resolver_mode": resolver_mode})


def evaluate_case(
    case: dict[str, Any], settings: Settings, llm_client=None
) -> dict[str, Any]:
    started_at = time.perf_counter()
    pipeline = build_pipeline(settings, llm_client=llm_client)
    try:
        output = pipeline.run(case["input"])
        result = {"status": "ok", "output": output}
    except DCNLError as exc:
        result = {"status": "error", "error": str(exc)}

    evaluation = score_case(case=case, result=result)
    evaluation["duration_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    return evaluation


def score_case(*, case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expected = case["expected_result"]
    if "error_type" in expected:
        return score_error_case(case=case, expected=expected, result=result)
    return score_success_case(case=case, expected=expected, result=result)


def score_error_case(
    *, case: dict[str, Any], expected: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    output = result.get("output", {})
    judge_decision = output.get("judge", {}).get("decision")
    passed = judge_decision == "reject"
    return {
        "id": case["id"],
        "input": case["input"],
        "kind": "expected_error",
        "passed": passed,
        "expected_result": expected,
        "actual_result": {
            "status": result["status"],
            "judge_decision": judge_decision,
            "reason_codes": output.get("judge", {}).get("reason_codes", []),
            "error": result.get("error"),
            "raw_output": output,
        },
    }


def score_success_case(
    *, case: dict[str, Any], expected: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    output = result.get("output", {})
    actual_resolved = output.get("resolved_query")
    judge_decision = output.get("judge", {}).get("decision")
    passed = (
        result["status"] == "ok"
        and compare_resolved_query(expected, actual_resolved)
        and judge_decision != "reject"
    )
    return {
        "id": case["id"],
        "input": case["input"],
        "kind": "expected_success",
        "passed": passed,
        "expected_result": expected,
        "actual_result": {
            "status": result["status"],
            "resolved_query": actual_resolved,
            "judge_decision": judge_decision,
            "error": result.get("error"),
            "raw_output": output,
        },
    }


def compare_resolved_query(
    expected: dict[str, Any], actual: dict[str, Any] | None
) -> bool:
    if actual is None:
        return False
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if isinstance(expected_value, list):
            if list(actual_value or []) != expected_value:
                return False
            continue
        if actual_value != expected_value:
            return False
    return True


def summarize(
    evaluations: list[dict[str, Any]],
    *,
    dataset_path: str,
    resolver_mode: str,
    max_workers: int,
) -> dict[str, Any]:
    total = len(evaluations)
    passed = sum(1 for item in evaluations if item["passed"])
    success_cases = [item for item in evaluations if item["kind"] == "expected_success"]
    error_cases = [item for item in evaluations if item["kind"] == "expected_error"]
    success_passed = sum(1 for item in success_cases if item["passed"])
    error_passed = sum(1 for item in error_cases if item["passed"])
    failed_cases = [item for item in evaluations if not item["passed"]]

    return {
        "dataset": dataset_path,
        "resolver_mode": resolver_mode,
        "max_workers": max_workers,
        "summary": {
            "total_cases": total,
            "passed_cases": passed,
            "accuracy": round(passed / total, 4) if total else 0.0,
            "success_cases": len(success_cases),
            "success_accuracy": round(success_passed / len(success_cases), 4)
            if success_cases
            else 0.0,
            "error_cases": len(error_cases),
            "error_accuracy": round(error_passed / len(error_cases), 4)
            if error_cases
            else 0.0,
        },
        "failed_cases": failed_cases,
        "evaluations": evaluations,
    }


def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    dataset = load_dataset(args.dataset)
    settings = make_settings(args.resolver_mode)
    llm_client = build_llm_client(settings)
    if llm_client is not None and args.max_rpm:
        llm_client = RateLimitedLLMClient(
            llm_client, rate_limiter=RateLimiter(max_rpm=args.max_rpm)
        )
    evaluations: list[dict[str, Any]] = []
    total = len(dataset)
    completed = 0

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [
            executor.submit(evaluate_case, case, settings, llm_client)
            for case in dataset
        ]
        for future in as_completed(futures):
            evaluations.append(future.result())
            completed += 1
            print(f"[eval] completed {completed}/{total}", file=sys.stderr, flush=True)

    evaluations.sort(key=lambda item: item["id"])
    report = summarize(
        evaluations,
        dataset_path=args.dataset,
        resolver_mode=args.resolver_mode,
        max_workers=args.max_workers,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report["output_path"] = str(output_path)

    return report


def main() -> int:
    args = parse_args()
    report = run_eval(args)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(
        json.dumps({"output_path": report["output_path"]}, ensure_ascii=False, indent=2)
    )
    if report["failed_cases"]:
        print(
            json.dumps(
                {"failed_cases": report["failed_cases"]}, ensure_ascii=False, indent=2
            )
        )
    return 0
