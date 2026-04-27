from __future__ import annotations

import json
import re
from dataclasses import dataclass

from dc_nl_cli.llm.base import LLMClient


TIME_ANALYZER_PROMPT = """Extract all temporal constraints mentioned in the user query.

Return JSON only in this shape:
{
  "signals": [
    {
      "kind": "year | range | latest | relative",
      "value": "string | null",
      "start": "string | null",
      "end": "string | null",
      "modifier": "string | null"
    }
  ]
}

Rules:
- Include all time-related signals mentioned in the query, even if they conflict.
- Use kind=year for a specific year.
- Use kind=range for year ranges.
- Use kind=latest for words like latest or most recent.
- Use kind=relative for vague phrases like around 2019 or recently.
- Keep modifier when words such as only, but, around appear near the time expression.
"""


@dataclass
class TimeSignals:
    signals: list[dict]


class TimeConstraintAnalyzer:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def analyze(self, query: str) -> TimeSignals:
        if self._llm_client:
            try:
                result = self._llm_client.generate_json(
                    prompt=TIME_ANALYZER_PROMPT, user_input=query
                )
                return TimeSignals(signals=result.get("signals", []))
            except Exception:
                pass
        return TimeSignals(signals=self._analyze_heuristically(query))

    def _analyze_heuristically(self, query: str) -> list[dict]:
        lowered = query.lower()
        signals: list[dict] = []

        for match in re.finditer(
            r"\bfrom\s+((?:19|20)\d{2})\s+(?:to|through|-)\s+((?:19|20)\d{2})\b",
            lowered,
        ):
            signals.append(
                {
                    "kind": "range",
                    "value": None,
                    "start": match.group(1),
                    "end": match.group(2),
                    "modifier": _find_modifier(lowered, match.start(), match.end()),
                }
            )

        for match in re.finditer(r"\b(19|20)\d{2}\b", lowered):
            signals.append(
                {
                    "kind": "year",
                    "value": match.group(0),
                    "start": None,
                    "end": None,
                    "modifier": _find_modifier(lowered, match.start(), match.end()),
                }
            )

        if any(token in lowered for token in ["latest", "most recent"]):
            signals.append(
                {
                    "kind": "latest",
                    "value": None,
                    "start": None,
                    "end": None,
                    "modifier": None,
                }
            )

        return _dedupe_signals(signals)


def _find_modifier(query: str, start: int, end: int) -> str | None:
    window = query[max(0, start - 12) : min(len(query), end + 12)]
    for modifier in ["only", "but", "around"]:
        if modifier in window:
            return modifier
    return None


def _dedupe_signals(signals: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for signal in signals:
        key = json.dumps(signal, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
    return deduped
