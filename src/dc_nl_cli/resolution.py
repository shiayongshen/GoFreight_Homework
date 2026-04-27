from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResolutionEvidence:
    selected: str | None
    selected_type: str | None = None
    selected_score: float | None = None
    candidates: list[dict] = field(default_factory=list)
    max_display_candidates: int = 5

    def to_dict(self) -> dict:
        return {
            "selected": self.selected,
            "selected_type": self.selected_type,
            "selected_score": self.selected_score,
            "candidates": self.candidates[: self.max_display_candidates],
        }
