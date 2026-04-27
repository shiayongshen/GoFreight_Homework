import pytest

from dc_nl_cli.errors import ResolutionError
from dc_nl_cli.resolvers.place_resolver import PlaceResolver


class StubClient:
    def __init__(self, candidates):
        self._candidates = candidates

    def resolve_place(self, query: str):
        return self._candidates


def test_place_resolver_hardrule_mode_without_rules_raises() -> None:
    resolver = PlaceResolver(StubClient([]), mode="hardrule")
    with pytest.raises(ResolutionError):
        resolver.resolve("Taiwan")


def test_place_resolver_api_mode_uses_first_candidate() -> None:
    resolver = PlaceResolver(
        StubClient([{"dcid": "geoId/13"}, {"dcid": "wikidataId/Q230"}]), mode="api"
    )
    assert resolver.resolve("Georgia") == "geoId/13"


def test_place_resolver_hybrid_without_api_candidates_raises() -> None:
    resolver = PlaceResolver(StubClient([]), mode="hybrid")
    with pytest.raises(ResolutionError):
        resolver.resolve("Taiwan")
