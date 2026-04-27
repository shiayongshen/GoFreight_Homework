from __future__ import annotations

from dc_nl_cli.errors import ResolutionError
from dc_nl_cli.resolution import ResolutionEvidence


class PlaceResolver:
    def __init__(self, datacommons_client, *, mode: str = "api") -> None:
        self._client = datacommons_client
        self._mode = mode

    def resolve(self, query: str) -> str:
        return self.resolve_with_evidence(query).selected

    def resolve_with_evidence(self, query: str) -> ResolutionEvidence:
        normalized = query.strip().lower()

        if self._mode == "hardrule":
            return self._resolve_from_aliases(query, normalized)

        try:
            return self._resolve_from_api(query)
        except ResolutionError:
            if self._mode == "hybrid":
                return self._resolve_from_aliases(query, normalized)
            raise

    def _resolve_from_aliases(
        self, query: str, normalized: str | None = None
    ) -> ResolutionEvidence:
        raise ResolutionError(f"could not resolve place with hard rules: {query}")

    def _resolve_from_api(self, query: str) -> ResolutionEvidence:
        candidates = self._client.resolve_place(query)
        if not candidates:
            raise ResolutionError(f"could not resolve place: {query}")
        selected = candidates[0]["dcid"]
        return ResolutionEvidence(
            selected=selected,
            selected_type="Place",
            candidates=candidates,
        )
