from __future__ import annotations

import re
from dataclasses import dataclass, field

from dc_nl_cli.parser.schema import CanonicalPayload
from dc_nl_cli.resolution import ResolutionEvidence
from dc_nl_cli.time_analysis import TimeSignals


@dataclass
class JudgeResult:
    decision: str
    confidence: float
    reason_codes: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reason_codes": self.reason_codes,
            "summary": self.summary,
        }


class ResolutionJudge:
    def judge(
        self,
        *,
        user_query: str,
        canonical_payload: CanonicalPayload,
        resolved_query: dict,
        time_signals: TimeSignals | None = None,
        stat_var_evidence: ResolutionEvidence | None = None,
    ) -> JudgeResult:
        reason_codes: list[str] = []

        if resolved_query.get("place") is None:
            return JudgeResult(
                decision="warn",
                confidence=0.65,
                reason_codes=["missing_place"],
                summary="Place was not specified; query was parsed but cannot be executed as an observation lookup.",
            )

        if canonical_payload.intent == "compare_places" and not resolved_query.get(
            "comparison_places"
        ):
            return JudgeResult(
                decision="reject",
                confidence=0.98,
                reason_codes=["missing_comparison_places"],
                summary="Compare query is missing resolved comparison places.",
            )

        if (
            canonical_payload.intent == "compare_places"
            and canonical_payload.comparison
        ):
            if (
                canonical_payload.comparison.operation == "difference"
                and len(resolved_query.get("comparison_places", [])) != 1
            ):
                return JudgeResult(
                    decision="reject",
                    confidence=0.98,
                    reason_codes=["invalid_difference_shape"],
                    summary="Difference queries require exactly two places total.",
                )

        time_reason = self._judge_time_conflict(
            canonical_payload=canonical_payload,
            time_signals=time_signals,
        )
        if time_reason:
            reason_codes.append(time_reason)

        metric_reason = self._judge_metric_relevance(
            metric_query=canonical_payload.metric_query,
            stat_var=resolved_query.get("stat_var"),
            stat_var_evidence=stat_var_evidence,
        )
        if metric_reason:
            reason_codes.append(metric_reason)

        if reason_codes:
            return JudgeResult(
                decision="reject",
                confidence=0.9,
                reason_codes=reason_codes,
                summary="Resolved statistical variable does not appear relevant to the requested metric.",
            )

        return JudgeResult(
            decision="accept",
            confidence=0.92,
            reason_codes=[],
            summary="Resolved query passed deterministic validation checks.",
        )

    def _judge_metric_relevance(
        self,
        *,
        metric_query: str,
        stat_var: str | None,
        stat_var_evidence: ResolutionEvidence | None,
    ) -> str | None:
        if not stat_var:
            return "missing_stat_var"
        if stat_var.startswith("dc/topic/"):
            return "topic_instead_of_stat_var"

        normalized_metric = _normalize_text(metric_query)
        candidate_text = _build_candidate_text(
            stat_var=stat_var, stat_var_evidence=stat_var_evidence
        )
        similarity = _token_overlap(normalized_metric, candidate_text)

        if stat_var_evidence and stat_var_evidence.selected_score is not None:
            if stat_var_evidence.selected_score < 0.65:
                return "low_stat_var_confidence"
            if (
                len(stat_var_evidence.candidates) > 1
                and stat_var_evidence.selected_score < 0.8
            ):
                top_score = stat_var_evidence.selected_score
                runner_up = next(
                    (
                        _candidate_score(candidate)
                        for candidate in stat_var_evidence.candidates
                        if candidate.get("dcid") != stat_var_evidence.selected
                    ),
                    None,
                )
                if runner_up is not None and abs(top_score - runner_up) < 0.02:
                    return "ambiguous_metric_resolution"

        if similarity < 0.2:
            return "low_metric_relevance"
        return None

    def _judge_time_conflict(
        self,
        *,
        canonical_payload: CanonicalPayload,
        time_signals: TimeSignals | None,
    ) -> str | None:
        if not time_signals:
            return None

        years = [
            signal for signal in time_signals.signals if signal.get("kind") == "year"
        ]
        ranges = [
            signal for signal in time_signals.signals if signal.get("kind") == "range"
        ]
        latest = [
            signal for signal in time_signals.signals if signal.get("kind") == "latest"
        ]

        if latest and (years or ranges):
            return "conflicting_time_constraints"
        if ranges and years:
            return "conflicting_time_constraints"
        distinct_years = {
            signal.get("value") for signal in years if signal.get("value")
        }
        if len(distinct_years) > 1 and any(
            signal.get("modifier") in {"only", "but"} for signal in years
        ):
            return "conflicting_time_constraints"
        if (
            canonical_payload.intent == "compare_places"
            and canonical_payload.comparison
        ):
            if (
                canonical_payload.comparison.operation
                in {"sum", "average", "min", "max", "rank", "difference"}
                and len(distinct_years) > 1
            ):
                return "conflicting_time_constraints"
        return None


def _candidate_score(candidate: dict) -> float | None:
    raw = candidate.get("metadata", {}).get("score")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _normalize_text(text: str) -> str:
    lowered = text.lower().replace("_", " ")
    lowered = re.sub(r"([a-z])([A-Z])", r"\1 \2", lowered)
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _build_candidate_text(
    *, stat_var: str, stat_var_evidence: ResolutionEvidence | None
) -> str:
    parts = [_normalize_text(stat_var)]
    if stat_var_evidence:
        for candidate in stat_var_evidence.candidates[:3]:
            if candidate.get("dcid") == stat_var_evidence.selected:
                sentence = candidate.get("metadata", {}).get("sentence")
                if sentence:
                    parts.append(_normalize_text(sentence))
                break
    return " ".join(part for part in parts if part)


def _token_overlap(left: str, right: str) -> float:
    left_tokens = {token for token in left.split() if token}
    right_tokens = {token for token in right.split() if token}
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    return len(intersection) / len(left_tokens)
