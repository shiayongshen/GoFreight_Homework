from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from dc_nl_cli.config import load_settings
from dc_nl_cli.errors import ConfigurationError, DCNLError
from dc_nl_cli.eval_runner import compare_resolved_query
from dc_nl_cli.llm.factory import build_llm_client
from dc_nl_cli.pipeline import build_pipeline


DEFAULT_OUTPUT = Path("eval/datasets/generated_cases.json")


@dataclass(frozen=True)
class SuccessBlueprint:
    id: str
    category: str
    tags: list[str]
    place_label: str | None
    place_dcid: str | None
    metric_label: str
    stat_var: str
    date: str
    comparison_places: list[dict[str, str]] | None = None
    comparison_operation: str | None = None
    style_notes: list[str] | None = None


@dataclass(frozen=True)
class ErrorBlueprint:
    id: str
    category: str
    tags: list[str]
    error_type: str
    failed_field: str
    style_notes: list[str]
    place_label: str | None = None
    metric_label: str | None = None


GENERATION_PROMPT = """
You generate adversarial natural-language eval queries for a Data Commons CLI.

Return strict JSON with this shape:
{
  "queries": [
    {"id": "case_001", "input": "natural language query here"}
  ]
}

Rules:
- Produce exactly one query per requested case id.
- Keep each query semantically equivalent to the structured target.
- Make the queries realistic, diverse, and slightly messy.
- Use typos, multilingual Chinese, ambiguity, or conflicting constraints only when the case blueprint asks for them.
- Do not explain your choices.
- Do not include markdown.
- Preserve the requested place, metric intent, date intent, and comparison structure.
- For missing-place cases, do not invent a geography.
- For unsupported-metric cases, keep the metric unsupported.
- For conflicting-time cases, keep the contradiction obvious in the wording.
""".strip()

REWRITE_PROMPT = """
You are revising one eval query for a Data Commons CLI.

Return strict JSON with this shape:
{
  "input": "revised query here"
}

Rules:
- Keep the query natural and realistic.
- Keep the query semantically equivalent to the target blueprint.
- Fix the exact mismatch described in the validation feedback.
- Do not explain anything.
- Do not include markdown.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a 30-case eval dataset using the configured LLM."
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT), help="Output JSON path."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output if it already exists.",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="Maximum validation/rewrite rounds per case.",
    )
    parser.add_argument(
        "--request-retries",
        type=int,
        default=3,
        help="Retries for transient LLM/API failures.",
    )
    return parser.parse_args()


def build_blueprints() -> list[SuccessBlueprint | ErrorBlueprint]:
    return [
        SuccessBlueprint(
            id="case_001",
            category="typo_metric",
            tags=["typo", "metric", "single_place", "single_year", "english"],
            place_label="USA",
            place_dcid="country/USA",
            metric_label="population",
            stat_var="Count_Person",
            date="2020",
            style_notes=["include one typo in the metric word"],
        ),
        SuccessBlueprint(
            id="case_002",
            category="typo_place",
            tags=["typo", "place", "single_place", "single_year", "english"],
            place_label="California",
            place_dcid="geoId/06",
            metric_label="GDP",
            stat_var="Amount_EconomicActivity_GrossDomesticProduction_Nominal",
            date="2018",
            style_notes=["include one typo in the place name"],
        ),
        SuccessBlueprint(
            id="case_003",
            category="typo_plus_ambiguous_place",
            tags=[
                "typo",
                "metric",
                "ambiguous_place",
                "compare",
                "single_year",
                "english",
            ],
            place_label="Japan",
            place_dcid="country/JPN",
            metric_label="unemployment rate",
            stat_var="UnemploymentRate_Person",
            date="2020",
            comparison_places=[{"label": "Korea", "dcid": "country/KOR"}],
            comparison_operation="compare",
            style_notes=[
                "include one typo in the metric phrase",
                "keep 'Korea' ambiguous-looking",
            ],
        ),
        SuccessBlueprint(
            id="case_004",
            category="typo_metric",
            tags=["typo", "metric", "single_place", "single_year", "english"],
            place_label="Texas",
            place_dcid="geoId/48",
            metric_label="median income",
            stat_var="Median_Income_Person",
            date="2021",
            style_notes=["include one typo in the metric phrase"],
        ),
        SuccessBlueprint(
            id="case_005",
            category="typo_multilingual_metric",
            tags=["typo", "multilingual", "metric", "single_place", "latest", "zh"],
            place_label="台灣",
            place_dcid="country/TWN",
            metric_label="人口",
            stat_var="Count_Person",
            date="LATEST",
            style_notes=[
                "write in Traditional Chinese",
                "include one typo or variant character in the metric",
            ],
        ),
        SuccessBlueprint(
            id="case_006",
            category="typo_operation",
            tags=[
                "typo",
                "aggregation",
                "operation",
                "compare",
                "single_year",
                "english",
            ],
            place_label="California",
            place_dcid="geoId/06",
            metric_label="GDP",
            stat_var="Amount_EconomicActivity_GrossDomesticProduction_Nominal",
            date="2018",
            comparison_places=[{"label": "Texas", "dcid": "geoId/48"}],
            comparison_operation="average",
            style_notes=["include one typo in the operation word"],
        ),
        SuccessBlueprint(
            id="case_007",
            category="ambiguous_place",
            tags=["ambiguous_place", "single_place", "single_year", "english"],
            place_label="Georgia",
            place_dcid="geoId/13",
            metric_label="GDP",
            stat_var="Amount_EconomicActivity_GrossDomesticProduction_Nominal",
            date="2018",
            style_notes=["leave the place name ambiguous"],
        ),
        SuccessBlueprint(
            id="case_008",
            category="ambiguous_place",
            tags=["ambiguous_place", "compare", "single_year", "english"],
            place_label="Congo",
            place_dcid="country/COD",
            metric_label="population",
            stat_var="Count_Person",
            date="2020",
            comparison_places=[{"label": "Japan", "dcid": "country/JPN"}],
            comparison_operation="compare",
            style_notes=["leave 'Congo' ambiguous"],
        ),
        SuccessBlueprint(
            id="case_009",
            category="mixed_ambiguity",
            tags=["ambiguous_place", "compare", "single_year", "english"],
            place_label="Taiwan",
            place_dcid="country/TWN",
            metric_label="unemployment rate",
            stat_var="UnemploymentRate_Person",
            date="2020",
            comparison_places=[{"label": "Georgia", "dcid": "geoId/13"}],
            comparison_operation="compare",
            style_notes=["use simple comparison wording"],
        ),
        SuccessBlueprint(
            id="case_010",
            category="underspecified_place",
            tags=["compare", "single_year", "english"],
            place_label="Japan",
            place_dcid="country/JPN",
            metric_label="unemployment rate",
            stat_var="UnemploymentRate_Person",
            date="2020",
            comparison_places=[{"label": "South Korea", "dcid": "country/KOR"}],
            comparison_operation="compare",
            style_notes=["use a clean comparison query"],
        ),
        ErrorBlueprint(
            id="case_011",
            category="constraint_conflict",
            tags=["conflict", "time", "range_vs_multiple_years", "english"],
            error_type="conflicting_time_constraints",
            failed_field="time",
            place_label="Taiwan",
            metric_label="population",
            style_notes=[
                "include explicit years 2020 and 2021",
                "also include a conflicting range 2010 to 2015",
            ],
        ),
        ErrorBlueprint(
            id="case_012",
            category="constraint_conflict",
            tags=["conflict", "time", "multiple_years", "compare", "english"],
            error_type="conflicting_time_constraints",
            failed_field="time",
            place_label="California and Texas",
            metric_label="GDP",
            style_notes=[
                "make it a comparison query",
                "mention 2018 and 2020 but also say only 2019",
            ],
        ),
        ErrorBlueprint(
            id="case_013",
            category="constraint_conflict",
            tags=["conflict", "time", "latest_vs_year", "english"],
            error_type="conflicting_time_constraints",
            failed_field="time",
            place_label="USA",
            metric_label="population",
            style_notes=["combine 'latest' with a specific year 2020"],
        ),
        ErrorBlueprint(
            id="case_014",
            category="constraint_conflict",
            tags=["conflict", "time", "range_vs_year", "english"],
            error_type="conflicting_time_constraints",
            failed_field="time",
            place_label="Japan",
            metric_label="unemployment rate",
            style_notes=["combine a range 2015 to 2020 with 'in 2018 only'"],
        ),
        ErrorBlueprint(
            id="case_015",
            category="constraint_conflict",
            tags=["conflict", "time", "rank", "latest_vs_multiple_years", "english"],
            error_type="conflicting_time_constraints",
            failed_field="time",
            place_label="California, Texas, and New York",
            metric_label="GDP",
            style_notes=[
                "make it a rank query",
                "mention 2018 and 2019",
                "also ask for a single latest value",
            ],
        ),
        ErrorBlueprint(
            id="case_016",
            category="constraint_conflict",
            tags=["conflict", "time", "aggregation", "range_vs_year", "english"],
            error_type="conflicting_time_constraints",
            failed_field="time",
            place_label="Japan and South Korea",
            metric_label="population",
            style_notes=[
                "make it an average query",
                "combine a range 2010 to 2020 with 'in 2018'",
            ],
        ),
        SuccessBlueprint(
            id="case_017",
            category="missing_place",
            tags=["missing_place", "demographic_slice", "latest", "english"],
            place_label=None,
            place_dcid=None,
            metric_label="female population over 85",
            stat_var="Count_Person_85OrMoreYears_Female",
            date="LATEST",
            style_notes=["do not mention any geography"],
        ),
        SuccessBlueprint(
            id="case_018",
            category="missing_place",
            tags=["missing_place", "single_year", "english"],
            place_label=None,
            place_dcid=None,
            metric_label="GDP",
            stat_var="Amount_EconomicActivity_GrossDomesticProduction_Nominal",
            date="2020",
            style_notes=["do not mention any geography"],
        ),
        SuccessBlueprint(
            id="case_019",
            category="missing_place",
            tags=["missing_place", "single_year", "english"],
            place_label=None,
            place_dcid=None,
            metric_label="unemployment rate",
            stat_var="UnemploymentRate_Person",
            date="2021",
            style_notes=["do not mention any geography"],
        ),
        ErrorBlueprint(
            id="case_020",
            category="unsupported_metric",
            tags=[
                "unsupported_metric",
                "multilingual",
                "single_place",
                "single_year",
                "zh",
            ],
            error_type="unsupported_metric",
            failed_field="stat_var",
            place_label="台灣",
            metric_label="快樂指數",
            style_notes=[
                "write in Traditional Chinese",
                "keep the unsupported metric explicit",
                "mention year 2020",
            ],
        ),
        ErrorBlueprint(
            id="case_021",
            category="unsupported_metric",
            tags=["unsupported_metric", "single_place", "single_year", "english"],
            error_type="unsupported_metric",
            failed_field="stat_var",
            place_label="Taiwan",
            metric_label="happiness",
            style_notes=["mention year 2020"],
        ),
        ErrorBlueprint(
            id="case_022",
            category="unsupported_metric",
            tags=["unsupported_metric", "single_place", "single_year", "english"],
            error_type="unsupported_metric",
            failed_field="stat_var",
            place_label="Japan",
            metric_label="weather score",
            style_notes=["mention year 2019"],
        ),
        SuccessBlueprint(
            id="case_023",
            category="sparse_time_specification",
            tags=["latest", "multilingual", "single_place", "zh"],
            place_label="台灣",
            place_dcid="country/TWN",
            metric_label="人口",
            stat_var="Count_Person",
            date="LATEST",
            style_notes=["write in Traditional Chinese", "omit any explicit year"],
        ),
        SuccessBlueprint(
            id="case_024",
            category="sparse_time_specification",
            tags=["latest", "single_place", "english"],
            place_label="Taiwan",
            place_dcid="country/TWN",
            metric_label="population",
            stat_var="Count_Person",
            date="LATEST",
            style_notes=["omit any explicit year"],
        ),
        SuccessBlueprint(
            id="case_025",
            category="range_query",
            tags=["range", "single_place", "english"],
            place_label="Japan",
            place_dcid="country/JPN",
            metric_label="population",
            stat_var="Count_Person",
            date="2010-2020",
            style_notes=["ask for a trend or series", "use years 2010 through 2020"],
        ),
        SuccessBlueprint(
            id="case_026",
            category="range_query",
            tags=["range", "single_place", "multilingual", "zh"],
            place_label="美國",
            place_dcid="country/USA",
            metric_label="失業率",
            stat_var="UnemploymentRate_Person",
            date="2015-2020",
            style_notes=[
                "write in Traditional Chinese",
                "ask for data from 2015 to 2020",
            ],
        ),
        SuccessBlueprint(
            id="case_027",
            category="aggregation_rank",
            tags=["rank", "compare", "single_year", "english"],
            place_label="California",
            place_dcid="geoId/06",
            metric_label="population",
            stat_var="Count_Person",
            date="2020",
            comparison_places=[
                {"label": "Texas", "dcid": "geoId/48"},
                {"label": "New York", "dcid": "geoId/36"},
            ],
            comparison_operation="rank",
            style_notes=["make it a ranking request"],
        ),
        SuccessBlueprint(
            id="case_028",
            category="aggregation_difference",
            tags=["difference", "compare", "single_year", "english"],
            place_label="Japan",
            place_dcid="country/JPN",
            metric_label="unemployment rate",
            stat_var="UnemploymentRate_Person",
            date="2020",
            comparison_places=[{"label": "South Korea", "dcid": "country/KOR"}],
            comparison_operation="difference",
            style_notes=["ask for the difference between the two places"],
        ),
        SuccessBlueprint(
            id="case_029",
            category="aggregation_sum",
            tags=["sum", "compare", "single_year", "english"],
            place_label="California",
            place_dcid="geoId/06",
            metric_label="population",
            stat_var="Count_Person",
            date="2020",
            comparison_places=[{"label": "Texas", "dcid": "geoId/48"}],
            comparison_operation="sum",
            style_notes=["ask for the total combined value"],
        ),
        SuccessBlueprint(
            id="case_030",
            category="aggregation_max",
            tags=["max", "compare", "single_year", "english"],
            place_label="California",
            place_dcid="geoId/06",
            metric_label="GDP",
            stat_var="Amount_EconomicActivity_GrossDomesticProduction_Nominal",
            date="2018",
            comparison_places=[
                {"label": "Texas", "dcid": "geoId/48"},
                {"label": "New York", "dcid": "geoId/36"},
            ],
            comparison_operation="max",
            style_notes=["ask which place has the highest value"],
        ),
    ]


def render_generation_payload(
    blueprints: list[SuccessBlueprint | ErrorBlueprint],
) -> str:
    cases: list[dict[str, Any]] = []
    for blueprint in blueprints:
        base: dict[str, Any] = {
            "id": blueprint.id,
            "category": blueprint.category,
            "tags": blueprint.tags,
            "style_notes": blueprint.style_notes,
        }
        if isinstance(blueprint, SuccessBlueprint):
            base["kind"] = "success"
            base["target"] = {
                "place_label": blueprint.place_label,
                "metric_label": blueprint.metric_label,
                "date": blueprint.date,
                "comparison_places": blueprint.comparison_places or [],
                "comparison_operation": blueprint.comparison_operation,
            }
        else:
            base["kind"] = "error"
            base["target"] = {
                "place_label": blueprint.place_label,
                "metric_label": blueprint.metric_label,
                "error_type": blueprint.error_type,
                "failed_field": blueprint.failed_field,
            }
        cases.append(base)
    return json.dumps({"cases": cases}, ensure_ascii=False, indent=2)


def render_single_blueprint(
    blueprint: SuccessBlueprint | ErrorBlueprint,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": blueprint.id,
        "category": blueprint.category,
        "tags": blueprint.tags,
        "style_notes": blueprint.style_notes,
    }
    if isinstance(blueprint, SuccessBlueprint):
        base["kind"] = "success"
        base["target"] = {
            "place_label": blueprint.place_label,
            "metric_label": blueprint.metric_label,
            "date": blueprint.date,
            "comparison_places": blueprint.comparison_places or [],
            "comparison_operation": blueprint.comparison_operation,
        }
    else:
        base["kind"] = "error"
        base["target"] = {
            "place_label": blueprint.place_label,
            "metric_label": blueprint.metric_label,
            "error_type": blueprint.error_type,
            "failed_field": blueprint.failed_field,
        }
    return base


def call_llm_json(
    llm_client, *, prompt: str, user_input: str, request_retries: int
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(request_retries + 1):
        try:
            return llm_client.generate_json(prompt=prompt, user_input=user_input)
        except (requests.RequestException, DCNLError, ValueError) as exc:
            last_error = exc
            if attempt == request_retries:
                break
            time.sleep(min(2**attempt, 5))
    raise ConfigurationError(
        f"LLM request failed after retries: {last_error}"
    ) from last_error


def generate_queries(
    blueprints: list[SuccessBlueprint | ErrorBlueprint],
    *,
    llm_client,
    request_retries: int,
) -> dict[str, str]:
    response = call_llm_json(
        llm_client,
        prompt=GENERATION_PROMPT,
        user_input=render_generation_payload(blueprints),
        request_retries=request_retries,
    )
    queries = response.get("queries")
    if not isinstance(queries, list):
        raise ConfigurationError(f"generator returned unexpected payload: {response}")

    query_map: dict[str, str] = {}
    for item in queries:
        if not isinstance(item, dict):
            continue
        case_id = item.get("id")
        query = item.get("input")
        if isinstance(case_id, str) and isinstance(query, str) and query.strip():
            query_map[case_id] = " ".join(query.strip().split())

    missing_ids = [
        blueprint.id for blueprint in blueprints if blueprint.id not in query_map
    ]
    if missing_ids:
        raise ConfigurationError(f"generator missed case ids: {missing_ids}")
    return query_map


def make_eval_case(
    blueprint: SuccessBlueprint | ErrorBlueprint, query: str
) -> dict[str, Any]:
    record = {
        "id": blueprint.id,
        "input": query,
        "category": blueprint.category,
        "tags": blueprint.tags,
    }
    if isinstance(blueprint, SuccessBlueprint):
        expected_result: dict[str, Any] = {
            "place": blueprint.place_dcid,
            "stat_var": blueprint.stat_var,
            "date": "" if "-" in blueprint.date else blueprint.date,
        }
        if blueprint.comparison_places:
            expected_result["comparison_places"] = [
                item["dcid"] for item in blueprint.comparison_places
            ]
        if blueprint.comparison_operation:
            expected_result["comparison_operation"] = blueprint.comparison_operation
        record["expected_result"] = expected_result
    else:
        record["expected_result"] = {
            "error_type": blueprint.error_type,
            "failed_field": blueprint.failed_field,
        }
    return record


def validate_query(
    pipeline, blueprint: SuccessBlueprint | ErrorBlueprint, query: str
) -> tuple[bool, str]:
    case = make_eval_case(blueprint, query)
    try:
        output = pipeline.run(query)
    except (DCNLError, requests.RequestException) as exc:
        if isinstance(blueprint, ErrorBlueprint):
            return False, f"parser/execution error before judge rejection: {exc}"
        return False, f"execution error: {exc}"

    expected = case["expected_result"]
    judge = output.get("judge", {})
    decision = judge.get("decision")
    resolved = output.get("resolved_query")

    if isinstance(blueprint, ErrorBlueprint):
        if decision == "reject":
            return True, "ok"
        return (
            False,
            f"expected judge reject for {blueprint.error_type}, got {decision!r}",
        )

    if decision == "reject":
        return False, f"unexpected judge rejection: {judge.get('reason_codes', [])}"
    if not compare_resolved_query(expected, resolved):
        return False, f"resolved_query mismatch: expected={expected}, actual={resolved}"
    return True, "ok"


def rewrite_query(
    llm_client,
    blueprint: SuccessBlueprint | ErrorBlueprint,
    query: str,
    feedback: str,
    *,
    request_retries: int,
) -> str:
    response = call_llm_json(
        llm_client,
        prompt=REWRITE_PROMPT,
        user_input=json.dumps(
            {
                "case": render_single_blueprint(blueprint),
                "current_query": query,
                "validation_feedback": feedback,
            },
            ensure_ascii=False,
            indent=2,
        ),
        request_retries=request_retries,
    )
    revised = response.get("input")
    if not isinstance(revised, str) or not revised.strip():
        raise ConfigurationError(f"rewrite returned unexpected payload: {response}")
    return " ".join(revised.strip().split())


def generate_verified_queries(
    blueprints: list[SuccessBlueprint | ErrorBlueprint],
    *,
    max_rounds: int,
    request_retries: int,
) -> dict[str, str]:
    settings = load_settings()
    llm_client = build_llm_client(settings)
    if llm_client is None:
        raise ConfigurationError(
            f"no LLM client could be built for provider={settings.llm_provider!r}; check your .env keys"
        )
    pipeline = build_pipeline(settings)
    query_map = generate_queries(
        blueprints, llm_client=llm_client, request_retries=request_retries
    )

    for blueprint in blueprints:
        query = query_map[blueprint.id]
        passed, feedback = validate_query(pipeline, blueprint, query)
        for _ in range(max_rounds):
            if passed:
                break
            query = rewrite_query(
                llm_client,
                blueprint,
                query,
                feedback,
                request_retries=request_retries,
            )
            passed, feedback = validate_query(pipeline, blueprint, query)
        query_map[blueprint.id] = query
    return query_map


def build_dataset(
    blueprints: list[SuccessBlueprint | ErrorBlueprint],
    query_map: dict[str, str],
) -> list[dict[str, Any]]:
    dataset: list[dict[str, Any]] = []
    for blueprint in blueprints:
        dataset.append(make_eval_case(blueprint, query_map[blueprint.id]))
    return dataset


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    if output_path.exists() and not args.overwrite:
        raise SystemExit(
            f"{output_path} already exists; pass --overwrite to replace it"
        )

    blueprints = build_blueprints()
    query_map = generate_verified_queries(
        blueprints,
        max_rounds=args.max_rounds,
        request_retries=args.request_retries,
    )
    dataset = build_dataset(blueprints, query_map)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {"output_path": str(output_path), "count": len(dataset)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
