from __future__ import annotations

from dc_nl_cli.errors import ResolutionError
from dc_nl_cli.resolution import ResolutionEvidence


class StatVarResolver:
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
        raise ResolutionError(f"could not resolve metric with hard rules: {query}")

    def _resolve_from_api(self, query: str) -> ResolutionEvidence:
        candidates = self._client.resolve_stat_var(query)
        if not candidates:
            raise ResolutionError(f"could not resolve metric: {query}")
        for candidate in candidates:
            if "StatisticalVariable" in candidate.get("typeOf", []):
                return ResolutionEvidence(
                    selected=candidate["dcid"],
                    selected_type="StatisticalVariable",
                    selected_score=_extract_score(candidate),
                    candidates=candidates,
                )
        top = candidates[0]
        return ResolutionEvidence(
            selected=top["dcid"],
            selected_type=(top.get("typeOf") or [None])[0],
            selected_score=_extract_score(top),
            candidates=candidates,
        )


def _extract_score(candidate: dict) -> float | None:
    raw_score = candidate.get("metadata", {}).get("score")
    if raw_score is None:
        return None
    try:
        return float(raw_score)
    except (TypeError, ValueError):
        return None
