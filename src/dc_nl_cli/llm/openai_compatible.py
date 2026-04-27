from __future__ import annotations

import json

import requests

from dc_nl_cli.errors import ExecutionError
from dc_nl_cli.llm.base import LLMClient


class OpenAICompatibleClient(LLMClient):
    def __init__(
        self, *, api_key: str, model: str, base_url: str, timeout: float = 30.0
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def generate_json(self, *, prompt: str, user_input: str) -> dict:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
        }
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        try:
            text = data["choices"][0]["message"]["content"]
            return json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ExecutionError(
                f"OpenAI-compatible provider returned an unexpected response: {data}"
            ) from exc


class OpenAIResponsesClient(LLMClient):
    def __init__(
        self, *, api_key: str, model: str, base_url: str, timeout: float = 30.0
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def generate_json(self, *, prompt: str, user_input: str) -> dict:
        url = f"{self._base_url}/responses"
        payload = {
            "model": self._model,
            "input": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
            "text": {
                "format": {"type": "json_object"},
            },
        }
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        try:
            text = data["output"][0]["content"][0]["text"]
            return json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ExecutionError(
                f"OpenAI Responses API returned an unexpected response: {data}"
            ) from exc
