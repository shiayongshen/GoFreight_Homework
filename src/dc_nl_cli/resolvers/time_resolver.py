from __future__ import annotations

from dc_nl_cli.parser.schema import TimeSpec


class TimeResolver:
    def resolve(self, time_spec: TimeSpec) -> dict:
        if time_spec.type == "year":
            return {"date": time_spec.value}
        if time_spec.type == "range":
            return {"date": ""}
        return {"date": "LATEST"}
