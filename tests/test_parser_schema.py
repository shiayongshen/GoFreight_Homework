from pydantic import ValidationError

from dc_nl_cli.parser.schema import CanonicalPayload


def test_schema_accepts_year_payload() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": "Taiwan",
            "metric_query": "population",
            "time": {"type": "year", "value": "2020"},
        }
    )
    assert payload.time.value == "2020"


def test_schema_accepts_null_place() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": None,
            "metric_query": "female population over 50",
            "time": {"type": "latest"},
        }
    )
    assert payload.place_query is None


def test_schema_normalizes_compare_places_without_primary_place() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "compare_places",
            "place_query": None,
            "metric_query": "unemployment rate",
            "time": {"type": "year", "value": "2020"},
            "comparison": {
                "places": ["Japan", "Korea"],
                "operation": "compare",
            },
        }
    )
    assert payload.place_query == "Japan"
    assert payload.comparison is not None
    assert payload.comparison.places == ["Korea"]


def test_schema_splits_rank_place_list_from_primary_field() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "compare_places",
            "place_query": "California, Texas, and New York",
            "metric_query": "GDP",
            "time": {"type": "year", "value": "2018"},
            "comparison": {"places": [], "operation": "rank"},
        }
    )
    assert payload.place_query == "California"
    assert payload.comparison is not None
    assert payload.comparison.places == ["Texas", "New York"]


def test_schema_rejects_invalid_latest_payload() -> None:
    try:
        CanonicalPayload.model_validate(
            {
                "intent": "get_stat_point",
                "place_query": "Taiwan",
                "metric_query": "population",
                "time": {"type": "latest", "value": "2020"},
            }
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("expected validation error")
