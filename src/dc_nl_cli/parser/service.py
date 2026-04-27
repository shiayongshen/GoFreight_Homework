from __future__ import annotations

import ast
import json
import re

from pydantic import ValidationError

from dc_nl_cli.errors import ParseError
from dc_nl_cli.llm.base import LLMClient
from dc_nl_cli.parser.prompt import PARSER_PROMPT
from dc_nl_cli.parser.schema import CanonicalPayload

PARSER_CORRECTION_PROMPT = """You fix malformed canonical payloads for a public-statistics query parser.

Return JSON only.

General guidelines:
- Return exactly one JSON object.
- Preserve the user's original intent.
- Preserve the original place, metric, time, and comparison meaning whenever possible.
- Remove any helper fields, duplicate interpretations, and explanation text.
- Do not return arrays at the top level.
- Do not serialize arrays or objects as strings.
- Use only these top-level keys when needed: intent, place_query, metric_query, time, comparison.
- Never return DCIDs or API URLs.
- `place_query` must be a string or null, never an array or object.
- `metric_query` must be a string.
- `comparison.places` must be a plain JSON array of strings, never a stringified array.
- The `time` field must always be an object, never a bare string or number.

Valid `time` shapes:
- latest -> {"type": "latest"}
- year 2020 -> {"type": "year", "value": "2020"}
- range 2018 to 2020 -> {"type": "range", "start": "2018", "end": "2020"}
""".strip()


class QueryParser:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def parse(self, query: str) -> CanonicalPayload:
        raw_payload = (
            self._parse_with_llm(query)
            if self._llm_client
            else self._parse_heuristically(query)
        )
        try:
            return CanonicalPayload.model_validate(
                _normalize_candidate_payload(raw_payload)
            )
        except ValidationError as exc:
            if self._llm_client:
                corrected_payload = self._repair_with_llm(query, raw_payload, str(exc))
                try:
                    return CanonicalPayload.model_validate(
                        _normalize_candidate_payload(corrected_payload)
                    )
                except ValidationError as corrected_exc:
                    raise ParseError(str(corrected_exc)) from corrected_exc
            raise ParseError(str(exc)) from exc

    def _parse_with_llm(self, query: str) -> dict:
        return self._llm_client.generate_json(prompt=PARSER_PROMPT, user_input=query)

    def _repair_with_llm(
        self, query: str, raw_payload: object, validation_error: str
    ) -> dict:
        repair_input = {
            "user_query": query,
            "candidate_payload": raw_payload,
            "validation_error": validation_error,
        }
        return self._llm_client.generate_json(
            prompt=PARSER_CORRECTION_PROMPT,
            user_input=json.dumps(repair_input, ensure_ascii=False, indent=2),
        )

    def _parse_heuristically(self, query: str) -> dict:
        normalized = " ".join(query.strip().split())
        lowered = normalized.lower()

        if not normalized:
            raise ParseError("query must not be empty")

        year_match = re.search(r"\b(19|20)\d{2}\b", lowered)
        range_match = re.search(
            r"\bfrom\s+((?:19|20)\d{2})\s+(?:to|through|-)\s+((?:19|20)\d{2})\b",
            lowered,
        )

        metric_aliases = {
            "population": ["population", "populaton", "人口"],
            "gdp": ["gdp", "gross domestic product"],
            "unemployment rate": ["unemployment", "unemployment rate"],
            "median income": ["income", "median income"],
        }
        metric_query = next(
            (
                metric
                for metric, terms in metric_aliases.items()
                if any(term in lowered for term in terms)
            ),
            "population",
        )

        operation = _detect_operation(lowered)
        if operation:
            places = _extract_compare_places(normalized)
            if len(places) < 2:
                raise ParseError("could not detect two places for comparison")
            primary, others = places[0], places[1:]
            time = (
                {
                    "type": "range",
                    "start": range_match.group(1),
                    "end": range_match.group(2),
                }
                if range_match
                else {"type": "year", "value": year_match.group(0)}
                if year_match
                else {"type": "latest"}
            )
            return {
                "intent": "compare_places",
                "place_query": primary,
                "metric_query": metric_query,
                "time": time,
                "comparison": {"places": others, "operation": operation},
            }

        place_query = _extract_place(normalized)

        if range_match:
            time = {
                "type": "range",
                "start": range_match.group(1),
                "end": range_match.group(2),
            }
            intent = "get_stat_series"
        elif year_match:
            time = {"type": "year", "value": year_match.group(0)}
            intent = "get_stat_point"
        else:
            time = {"type": "latest"}
            intent = "get_stat_point"

        return {
            "intent": intent,
            "place_query": place_query,
            "metric_query": metric_query,
            "time": time,
        }


def _detect_operation(lowered_query: str) -> str | None:
    if any(token in lowered_query for token in ["average", "avg", "mean"]):
        return "average"
    if any(token in lowered_query for token in ["sum", "total"]):
        return "sum"
    if any(token in lowered_query for token in ["difference", "minus"]):
        return "difference"
    if any(
        token in lowered_query
        for token in ["rank", "highest to lowest", "lowest to highest"]
    ):
        return "rank"
    if any(
        token in lowered_query for token in ["maximum", "max", "highest", "largest"]
    ):
        return "max"
    if any(
        token in lowered_query for token in ["minimum", "min", "lowest", "smallest"]
    ):
        return "min"
    if any(token in lowered_query for token in ["compare", "higher", "vs", "versus"]):
        return "compare"
    return None


def _extract_compare_places(query: str) -> list[str]:
    of_match = re.search(
        r"\b(?:of|between|among|across)\s+([A-Za-z\u4e00-\u9fff\s,]+?)(?:\s+in\s+\d{4}|\s+from\s+\d{4}|$|\?)",
        query,
        flags=re.IGNORECASE,
    )
    if of_match:
        extracted = _split_places(of_match.group(1))
        if len(extracted) >= 2:
            return extracted
    if " and " in query.lower() or "," in query:
        extracted = _split_places(query)
        if len(extracted) >= 2:
            return extracted
    if " vs " in query.lower():
        left, right = re.split(r"\bvs\b", query, maxsplit=1, flags=re.IGNORECASE)
        return [left.strip(" ?.,").split()[-1], right.strip(" ?.,").split()[0]]
    return []


def _split_places(text: str) -> list[str]:
    scrubbed = re.sub(
        r"\b(?:average|avg|mean|sum|total|difference|rank|compare|max|min|highest|lowest|largest|smallest|gdp|population|unemployment rate|median income|by)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    scrubbed = scrubbed.replace(" versus ", ",").replace(" vs ", ",")
    parts = re.split(r",|\band\b", scrubbed, flags=re.IGNORECASE)
    places = [part.strip(" ?.,") for part in parts if part.strip(" ?.,")]
    return places


def _extract_place(query: str) -> str | None:
    patterns = [
        r"\bof\s+([A-Za-z\u4e00-\u9fff\s]+?)(?:\s+in\s+\d{4}|\s+from\s+\d{4}|$|\?)",
        r"\bfor\s+([A-Za-z\u4e00-\u9fff\s]+?)(?:\s+in\s+\d{4}|\s+from\s+\d{4}|$|\?)",
        r"^([A-Za-z\u4e00-\u9fff\s]+?)\s+\d{4}",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" ?.,")
    return None


def _normalize_candidate_payload(payload: object) -> object:
    if isinstance(payload, list):
        if len(payload) == 1:
            return _normalize_candidate_payload(payload[0])
        return [_normalize_candidate_payload(item) for item in payload]

    if isinstance(payload, str):
        parsed = _try_parse_embedded_structure(payload)
        return _normalize_candidate_payload(parsed) if parsed is not None else payload

    if isinstance(payload, dict):
        normalized = {
            key: _normalize_candidate_payload(value) for key, value in payload.items()
        }
        if set(normalized) == {"payload"}:
            return _normalize_candidate_payload(normalized["payload"])
        comparison = normalized.get("comparison")
        if isinstance(comparison, dict):
            places = comparison.get("places")
            if isinstance(places, str):
                parsed_places = _try_parse_embedded_structure(places)
                if isinstance(parsed_places, list):
                    comparison["places"] = [str(item) for item in parsed_places]
        return normalized

    return payload


def _try_parse_embedded_structure(value: str) -> object | None:
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped.strip("`").strip()
    repaired = re.sub(r'""([A-Za-z_][A-Za-z0-9_]*)""(?=\s*:)', r'"\1"', stripped)
    for candidate in (repaired, stripped):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        try:
            return ast.literal_eval(candidate)
        except (ValueError, SyntaxError):
            pass
    return None
