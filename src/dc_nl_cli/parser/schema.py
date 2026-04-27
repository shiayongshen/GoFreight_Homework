from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Intent = Literal["get_stat_point", "get_stat_series", "compare_places"]
TimeType = Literal["year", "range", "latest"]
ComparisonOperation = Literal[
    "compare", "rank", "difference", "sum", "average", "min", "max"
]


class TimeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: TimeType
    value: str | None = None
    start: str | None = None
    end: str | None = None

    @field_validator("value", "start", "end", mode="before")
    @classmethod
    def coerce_to_string(cls, value):
        if value is None:
            return None
        return str(value)

    @model_validator(mode="after")
    def validate_shape(self) -> "TimeSpec":
        if self.type == "year" and not self.value:
            raise ValueError("year time spec requires value")
        if self.type == "range" and (not self.start or not self.end):
            raise ValueError("range time spec requires start and end")
        if self.type == "latest" and any([self.value, self.start, self.end]):
            raise ValueError("latest time spec must not include value/start/end")
        return self


class ComparisonSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    places: list[str] = Field(default_factory=list)
    operation: ComparisonOperation = "compare"

    @field_validator("places", mode="before")
    @classmethod
    def coerce_places(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]


class CanonicalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    place_query: str | None = None
    metric_query: str
    time: TimeSpec
    comparison: ComparisonSpec | None = None

    @field_validator("place_query", "metric_query", mode="before")
    @classmethod
    def coerce_text_fields(cls, value):
        if value is None:
            return None
        return str(value)

    @model_validator(mode="after")
    def validate_comparison(self) -> "CanonicalPayload":
        if self.intent == "compare_places":
            if self.comparison and not self.comparison.places and self.place_query:
                split_places = _split_place_list(self.place_query)
                if len(split_places) >= 2:
                    self.place_query = split_places[0]
                    self.comparison.places = split_places[1:]
            if not self.comparison or not self.comparison.places:
                raise ValueError("compare_places requires comparison places")
            if self.place_query is None and len(self.comparison.places) >= 2:
                self.place_query = self.comparison.places[0]
                self.comparison.places = self.comparison.places[1:]
            self.comparison.places = [
                place for place in self.comparison.places if place != self.place_query
            ]
            if not self.comparison.places:
                raise ValueError(
                    "compare_places requires at least one distinct comparison place"
                )
            if (
                self.comparison.operation == "difference"
                and len(self.comparison.places) != 1
            ):
                raise ValueError("difference requires exactly two places total")
        return self


def _split_place_list(text: str) -> list[str]:
    scrubbed = re.sub(r"\bby\s+[A-Za-z\s]+\b", "", text, flags=re.IGNORECASE)
    parts = re.split(r",|\band\b", scrubbed, flags=re.IGNORECASE)
    return [part.strip(" ?.,") for part in parts if part.strip(" ?.,")]
