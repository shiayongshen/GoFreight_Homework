from __future__ import annotations

from dc_nl_cli.parser.service import QueryParser


class StubLLMClient:
    def __init__(self, responses):
        self._responses = list(responses)

    def generate_json(self, *, prompt: str, user_input: str):
        if not self._responses:
            raise AssertionError("no more stub responses")
        return self._responses.pop(0)


def test_parser_unwraps_single_item_top_level_list() -> None:
    parser = QueryParser(
        llm_client=StubLLMClient(
            [
                [
                    {
                        "intent": "get_stat_point",
                        "place_query": "Taiwan",
                        "metric_query": "population",
                        "time": {"type": "year", "value": "2020"},
                    }
                ]
            ]
        )
    )

    payload = parser.parse("What was Taiwan's population in 2020?")

    assert payload.place_query == "Taiwan"
    assert payload.time.value == "2020"


def test_parser_repairs_stringified_comparison_places() -> None:
    parser = QueryParser(
        llm_client=StubLLMClient(
            [
                {
                    "intent": "compare_places",
                    "place_query": "California",
                    "metric_query": "population",
                    "time": {"type": "year", "value": "2020"},
                    "comparison": {
                        "places": "['Texas', 'New York']",
                        "operation": "rank",
                    },
                }
            ]
        )
    )

    payload = parser.parse("Rank California, Texas, and New York by population in 2020")

    assert payload.comparison is not None
    assert payload.comparison.places == ["Texas", "New York"]


def test_parser_uses_llm_correction_after_validation_error() -> None:
    parser = QueryParser(
        llm_client=StubLLMClient(
            [
                {
                    "intent": "get_stat_point",
                    "place_query": "Taiwan",
                    "metric_query": "population",
                    "time": {"type": "year", "value": "2020"},
                    "additional_times": [{"type": "year", "value": "2021"}],
                },
                {
                    "intent": "get_stat_point",
                    "place_query": "Taiwan",
                    "metric_query": "population",
                    "time": {"type": "year", "value": "2020"},
                },
            ]
        )
    )

    payload = parser.parse("What was Taiwan's population in 2020?")

    assert payload.place_query == "Taiwan"
    assert payload.time.value == "2020"


def test_parser_repairs_string_latest_time_with_llm_correction() -> None:
    parser = QueryParser(
        llm_client=StubLLMClient(
            [
                {
                    "intent": "get_stat_point",
                    "place_query": "Taiwan",
                    "metric_query": "population",
                    "time": "latest",
                },
                {
                    "intent": "get_stat_point",
                    "place_query": "Taiwan",
                    "metric_query": "population",
                    "time": {"type": "latest"},
                },
            ]
        )
    )

    payload = parser.parse("What is the population of Taiwan?")

    assert payload.place_query == "Taiwan"
    assert payload.time.type == "latest"


def test_parser_repairs_list_place_query_with_llm_correction() -> None:
    parser = QueryParser(
        llm_client=StubLLMClient(
            [
                {
                    "intent": "get_stat_point",
                    "place_query": ["Taiwan"],
                    "metric_query": "population",
                    "time": {"type": "latest"},
                },
                {
                    "intent": "get_stat_point",
                    "place_query": "Taiwan",
                    "metric_query": "population",
                    "time": {"type": "latest"},
                },
            ]
        )
    )

    payload = parser.parse("What is the population of Taiwan?")

    assert payload.place_query == "Taiwan"
    assert payload.time.type == "latest"
