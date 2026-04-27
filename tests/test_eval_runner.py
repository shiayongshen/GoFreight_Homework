import argparse

from dc_nl_cli.eval_runner import (
    compare_resolved_query,
    score_error_case,
    score_success_case,
)


def test_compare_resolved_query_matches_exact_keys() -> None:
    assert compare_resolved_query(
        {
            "place": "country/USA",
            "stat_var": "Count_Person",
            "date": "2020",
            "comparison_places": ["country/CAN"],
        },
        {
            "place": "country/USA",
            "stat_var": "Count_Person",
            "date": "2020",
            "comparison_places": ["country/CAN"],
            "comparison_operation": "compare",
        },
    )


def test_score_error_case_uses_judge_reject() -> None:
    evaluation = score_error_case(
        case={"id": "case_x", "input": "bad"},
        expected={"error_type": "unsupported_metric"},
        result={
            "status": "ok",
            "output": {
                "judge": {
                    "decision": "reject",
                    "reason_codes": ["unsupported_metric_relevance"],
                }
            },
        },
    )
    assert evaluation["passed"] is True


def test_score_success_case_compares_resolved_query() -> None:
    evaluation = score_success_case(
        case={"id": "case_y", "input": "good"},
        expected={"place": "country/USA", "stat_var": "Count_Person", "date": "2020"},
        result={
            "status": "ok",
            "output": {
                "resolved_query": {
                    "place": "country/USA",
                    "stat_var": "Count_Person",
                    "date": "2020",
                },
                "judge": {"decision": "accept"},
            },
        },
    )
    assert evaluation["passed"] is True


def test_run_eval_accepts_max_rpm(monkeypatch, tmp_path) -> None:
    from dc_nl_cli import eval_runner

    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "report.json"
    dataset_path.write_text(
        '[{"id":"case_001","input":"x","expected_result":{"place":"country/USA","stat_var":"Count_Person","date":"2020"}}]',
        encoding="utf-8",
    )

    monkeypatch.setattr(eval_runner, "build_llm_client", lambda settings: object())
    monkeypatch.setattr(
        eval_runner,
        "evaluate_case",
        lambda case, settings, llm_client=None: {
            "id": case["id"],
            "kind": "expected_success",
            "passed": True,
        },
    )

    args = argparse.Namespace(
        dataset=str(dataset_path),
        resolver_mode="api",
        max_workers=1,
        max_rpm=30.0,
        output=str(output_path),
    )
    report = eval_runner.run_eval(args)

    assert report["summary"]["accuracy"] == 1.0
