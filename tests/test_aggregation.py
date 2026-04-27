from dc_nl_cli.datacommons.query_builder import QueryBuilder
from dc_nl_cli.parser.service import QueryParser


def test_parser_detects_average_operation() -> None:
    payload = QueryParser().parse("average GDP of California and Texas in 2018")
    assert payload.intent == "compare_places"
    assert payload.comparison is not None
    assert payload.comparison.operation == "average"
    assert payload.place_query == "California"
    assert payload.comparison.places == ["Texas"]


def test_query_builder_aggregates_sum() -> None:
    result = QueryBuilder().aggregate_results(
        operation="sum",
        place_results=[
            {"place": "geoId/06", "value": 3, "date": "2018"},
            {"place": "geoId/48", "value": 5, "date": "2018"},
        ],
        date="2018",
    )
    assert result["value"] == 8


def test_query_builder_aggregates_average() -> None:
    result = QueryBuilder().aggregate_results(
        operation="average",
        place_results=[
            {"place": "geoId/06", "value": 3, "date": "2018"},
            {"place": "geoId/48", "value": 5, "date": "2018"},
        ],
        date="2018",
    )
    assert result["value"] == 4


def test_query_builder_aggregates_difference() -> None:
    result = QueryBuilder().aggregate_results(
        operation="difference",
        place_results=[
            {"place": "geoId/06", "value": 8, "date": "2018"},
            {"place": "geoId/48", "value": 5, "date": "2018"},
        ],
        date="2018",
    )
    assert result["value"] == 3


def test_query_builder_aggregates_rank() -> None:
    result = QueryBuilder().aggregate_results(
        operation="rank",
        place_results=[
            {"place": "geoId/06", "value": 3, "date": "2018"},
            {"place": "geoId/48", "value": 5, "date": "2018"},
        ],
        date="2018",
    )
    assert [item["place"] for item in result["places"]] == ["geoId/48", "geoId/06"]


def test_query_builder_aggregates_min_and_max() -> None:
    min_result = QueryBuilder().aggregate_results(
        operation="min",
        place_results=[
            {"place": "geoId/06", "value": 3, "date": "2018"},
            {"place": "geoId/48", "value": 5, "date": "2018"},
        ],
        date="2018",
    )
    max_result = QueryBuilder().aggregate_results(
        operation="max",
        place_results=[
            {"place": "geoId/06", "value": 3, "date": "2018"},
            {"place": "geoId/48", "value": 5, "date": "2018"},
        ],
        date="2018",
    )
    assert min_result["place"] == "geoId/06"
    assert max_result["place"] == "geoId/48"
