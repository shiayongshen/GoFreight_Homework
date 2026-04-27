from __future__ import annotations

from dc_nl_cli.parser.schema import CanonicalPayload


class QueryBuilder:
    def build(
        self,
        *,
        payload: CanonicalPayload,
        place_dcid: str | None,
        stat_var_dcid: str,
        date: str,
        comparison_place_dcids: list[str] | None = None,
    ) -> dict:
        query = {
            "place": place_dcid,
            "stat_var": stat_var_dcid,
            "date": date,
        }
        if payload.intent == "compare_places" and payload.comparison:
            query["comparison_places"] = (
                comparison_place_dcids or payload.comparison.places
            )
            query["comparison_operation"] = payload.comparison.operation
        return query

    def normalize_result(
        self, *, raw_response: dict, place_dcid: str, stat_var_dcid: str, date: str
    ) -> dict:
        by_variable = raw_response.get("byVariable", {})
        by_entity = by_variable.get(stat_var_dcid, {}).get("byEntity", {})
        entity_data = by_entity.get(place_dcid, {})
        ordered_facets = entity_data.get("orderedFacets", [])
        if not ordered_facets:
            return {"value": None, "date": None}

        observations = ordered_facets[0].get("observations", [])
        if date == "" and observations:
            return {"series": observations}
        if not observations:
            return {"value": None, "date": None}
        observation = observations[0]
        return {
            "value": observation.get("value"),
            "date": observation.get("date"),
        }

    def aggregate_results(
        self, *, operation: str, place_results: list[dict], date: str
    ) -> dict:
        if date == "":
            if operation != "compare":
                return {
                    "error": "aggregation over time series is not supported in the baseline",
                    "series_by_place": place_results,
                }
            return {"places": place_results}

        valid = [result for result in place_results if result.get("value") is not None]
        if not valid:
            return {"value": None, "date": None}

        if operation == "compare":
            return {"places": place_results}
        if operation == "difference":
            if len(valid) != 2:
                return {
                    "error": "difference requires exactly two place values",
                    "places": place_results,
                }
            return {
                "value": valid[0]["value"] - valid[1]["value"],
                "date": valid[0]["date"],
                "places": place_results,
            }
        if operation == "rank":
            return {
                "places": sorted(
                    place_results,
                    key=lambda item: (item["value"] is None, -(item["value"] or 0)),
                )
            }
        if operation == "sum":
            return {
                "value": sum(item["value"] for item in valid),
                "date": valid[0]["date"],
                "places": place_results,
            }
        if operation == "average":
            return {
                "value": sum(item["value"] for item in valid) / len(valid),
                "date": valid[0]["date"],
                "places": place_results,
            }
        if operation == "min":
            selected = min(valid, key=lambda item: item["value"])
            return {
                "value": selected["value"],
                "date": selected["date"],
                "place": selected["place"],
                "places": place_results,
            }
        if operation == "max":
            selected = max(valid, key=lambda item: item["value"])
            return {
                "value": selected["value"],
                "date": selected["date"],
                "place": selected["place"],
                "places": place_results,
            }
        return {"places": place_results}
