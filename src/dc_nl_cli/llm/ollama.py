from __future__ import annotations

import json

import requests

from dc_nl_cli.errors import ExecutionError
from dc_nl_cli.llm.base import LLMClient


class OllamaClient(LLMClient):
    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        timeout: float = 30.0,
        api_key: str | None = None,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._api_key = api_key

    def generate_json(self, *, prompt: str, user_input: str) -> dict:
        url = f"{self._base_url}/chat"
        payload = {
            "model": self._model,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
            },
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        try:
            text = data["message"]["content"]
            return json.loads(text)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ExecutionError(
                f"Ollama returned an unexpected response: {data}"
            ) from exc
