from __future__ import annotations

import threading
import time

from dc_nl_cli.llm.base import LLMClient


class RateLimiter:
    def __init__(self, *, max_rpm: float) -> None:
        if max_rpm <= 0:
            raise ValueError("max_rpm must be positive")
        self._min_interval_seconds = 60.0 / max_rpm
        self._lock = threading.Lock()
        self._last_call_started_at = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait_seconds = self._min_interval_seconds - (
                now - self._last_call_started_at
            )
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_call_started_at = time.monotonic()


class RateLimitedLLMClient(LLMClient):
    def __init__(self, wrapped: LLMClient, *, rate_limiter: RateLimiter) -> None:
        self._wrapped = wrapped
        self._rate_limiter = rate_limiter

    def generate_json(self, *, prompt: str, user_input: str) -> dict:
        self._rate_limiter.wait()
        return self._wrapped.generate_json(prompt=prompt, user_input=user_input)
