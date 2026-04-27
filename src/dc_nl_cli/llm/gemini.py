from __future__ import annotations

import ast
import json
import re

import requests

from dc_nl_cli.errors import ExecutionError
from dc_nl_cli.llm.base import LLMClient


class GeminiClient(LLMClient):
    def __init__(
        self, *, api_key: str, model: str, base_url: str, timeout: float = 30.0
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def generate_json(self, *, prompt: str, user_input: str) -> dict:
        url = f"{self._base_url}/models/{self._model}:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{prompt}\n\nUser query:\n{user_input}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
        response = requests.post(
            url,
            params={"key": self._api_key},
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return _load_json_leniently(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ExecutionError(
                f"Gemini returned an unexpected response: {data}"
            ) from exc


def _load_json_leniently(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped.strip("`").strip()
    repaired = re.sub(r'""([A-Za-z_][A-Za-z0-9_]*)""(?=\s*:)', r'"\1"', stripped)
    for candidate in (repaired, stripped):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
            return {"payload": parsed}
        except json.JSONDecodeError:
            pass
        try:
            parsed = ast.literal_eval(candidate)
            if isinstance(parsed, dict):
                return parsed
            return {"payload": parsed}
        except (ValueError, SyntaxError):
            pass
    raise json.JSONDecodeError("could not decode model JSON", stripped, 0)
