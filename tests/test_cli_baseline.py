import json

from dc_nl_cli import cli


class StubPipeline:
    def run(self, query: str) -> dict:
        return {
            "input": query,
            "canonical_payload": {
                "intent": "get_stat_point",
                "place_query": "Taiwan",
                "metric_query": "population",
                "time": {"type": "year", "value": "2020"},
            },
            "resolved_query": {
                "place": "country/TWN",
                "stat_var": "Count_Person",
                "date": "2020",
            },
            "result": {"value": 23500000, "date": "2020"},
            "judge": {
                "decision": "accept",
                "confidence": 0.92,
                "reason_codes": [],
                "summary": "Resolved query passed deterministic validation checks.",
            },
        }


def test_cli_emits_json(monkeypatch, capsys) -> None:
    captured_settings = {}

    def fake_build_pipeline(settings):
        captured_settings["resolver_mode"] = settings.resolver_mode
        return StubPipeline()

    monkeypatch.setattr(cli, "build_pipeline", fake_build_pipeline)
    monkeypatch.setattr(
        "sys.argv",
        [
            "dc-query",
            "--resolver-mode",
            "hybrid",
            "What was Taiwan's population in 2020?",
        ],
    )

    exit_code = cli.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["resolved_query"]["place"] == "country/TWN"
    assert captured_settings["resolver_mode"] == "hybrid"


def test_cli_allows_missing_place(monkeypatch, capsys) -> None:
    class PartialPipeline:
        def run(self, query: str) -> dict:
            return {
                "input": query,
                "canonical_payload": {
                    "intent": "get_stat_point",
                    "metric_query": "female population over 50",
                    "time": {"type": "latest"},
                },
                "resolved_query": {
                    "place": None,
                    "stat_var": "Count_Person_50OrMoreYears_Female",
                    "date": "LATEST",
                },
                "result": None,
                "warning": "place was not specified; query was parsed but not executed",
                "judge": {
                    "decision": "warn",
                    "confidence": 0.65,
                    "reason_codes": ["missing_place"],
                    "summary": "Place was not specified; query was parsed but cannot be executed as an observation lookup.",
                },
            }

    monkeypatch.setattr(cli, "build_pipeline", lambda settings: PartialPipeline())
    monkeypatch.setattr("sys.argv", ["dc-query", "female population over 50"])

    exit_code = cli.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["resolved_query"]["place"] is None
    assert "not executed" in payload["warning"]
    assert payload["judge"]["decision"] == "warn"
