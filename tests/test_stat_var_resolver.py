import pytest

from dc_nl_cli.errors import ResolutionError
from dc_nl_cli.resolvers.stat_var_resolver import StatVarResolver


class StubClient:
    def __init__(self, candidates=None):
        self._candidates = (
            [{"dcid": "Test_Variable"}] if candidates is None else candidates
        )

    def resolve_stat_var(self, query: str):
        return self._candidates


def test_stat_var_resolver_hardrule_mode_without_rules_raises() -> None:
    resolver = StatVarResolver(StubClient(), mode="hardrule")
    with pytest.raises(ResolutionError):
        resolver.resolve("population")


def test_stat_var_resolver_falls_back_to_client() -> None:
    resolver = StatVarResolver(StubClient(), mode="api")
    assert resolver.resolve("custom metric") == "Test_Variable"


def test_stat_var_resolver_hybrid_without_api_candidates_raises() -> None:
    resolver = StatVarResolver(StubClient(candidates=[]), mode="hybrid")
    with pytest.raises(ResolutionError):
        resolver.resolve("population")


def test_stat_var_resolver_prefers_statistical_variable_candidate() -> None:
    resolver = StatVarResolver(
        StubClient(
            candidates=[
                {"dcid": "dc/topic/GDP", "typeOf": ["Topic"]},
                {
                    "dcid": "Amount_EconomicActivity_GrossDomesticProduction",
                    "typeOf": ["StatisticalVariable"],
                },
            ]
        ),
        mode="api",
    )
    assert resolver.resolve("GDP") == "Amount_EconomicActivity_GrossDomesticProduction"


def test_stat_var_resolver_returns_evidence_with_score() -> None:
    resolver = StatVarResolver(
        StubClient(
            candidates=[
                {
                    "dcid": "Median_Income_Person",
                    "typeOf": ["StatisticalVariable"],
                    "metadata": {"score": "0.91"},
                }
            ]
        ),
        mode="api",
    )
    evidence = resolver.resolve_with_evidence("median income")
    assert evidence.selected == "Median_Income_Person"
    assert evidence.selected_score == 0.91
