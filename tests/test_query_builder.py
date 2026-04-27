from dc_nl_cli.datacommons.query_builder import QueryBuilder
from dc_nl_cli.parser.schema import CanonicalPayload


def test_query_builder_builds_point_query() -> None:
    payload = CanonicalPayload.model_validate(
        {
            "intent": "get_stat_point",
            "place_query": "Taiwan",
            "metric_query": "population",
            "time": {"type": "year", "value": "2020"},
        }
    )
    query = QueryBuilder().build(
        payload=payload,
        place_dcid="country/TWN",
        stat_var_dcid="Count_Person",
        date="2020",
    )
    assert query == {
        "place": "country/TWN",
        "stat_var": "Count_Person",
        "date": "2020",
    }


def test_query_builder_normalizes_series_response() -> None:
    result = QueryBuilder().normalize_result(
        raw_response={
            "byVariable": {
                "Count_Person": {
                    "byEntity": {
                        "country/TWN": {
                            "orderedFacets": [
                                {
                                    "observations": [
                                        {"date": "2020", "value": 23},
                                        {"date": "2021", "value": 24},
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        },
        place_dcid="country/TWN",
        stat_var_dcid="Count_Person",
        date="",
    )
    assert result == {
        "series": [{"date": "2020", "value": 23}, {"date": "2021", "value": 24}]
    }
