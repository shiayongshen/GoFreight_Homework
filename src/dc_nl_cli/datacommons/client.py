from __future__ import annotations

from typing import Any

import requests

from dc_nl_cli.errors import ExecutionError


class DataCommonsClient:
    def __init__(self, *, api_key: str, base_url: str, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def resolve_place(self, query: str) -> list[dict[str, Any]]:
        data = self._post(
            "/resolve",
            {
                "nodes": [query],
                "property": "<-description->dcid",
            },
        )
        return data.get("entities", [{}])[0].get("candidates", [])

    def resolve_stat_var(self, query: str) -> list[dict[str, Any]]:
        data = self._post(
            "/resolve",
            {
                "nodes": [query],
                "resolver": "indicator",
                "property": "<-description->dcid",
            },
        )
        return data.get("entities", [{}])[0].get("candidates", [])

    def get_observations(
        self, *, place_dcid: str, stat_var_dcid: str, date: str
    ) -> dict[str, Any]:
        return self._post(
            "/observation",
            {
                "date": date,
                "entity": {"dcids": [place_dcid]},
                "variable": {"dcids": [stat_var_dcid]},
                "select": ["entity", "variable", "date", "value"],
            },
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self._base_url}{path}",
            headers={"X-API-Key": self._api_key},
            json=payload,
            timeout=self._timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise ExecutionError(
                f"Data Commons request failed: {response.text}"
            ) from exc
        return response.json()
