from __future__ import annotations

from dc_nl_cli.llm.base import LLMClient
from dc_nl_cli.llm.wrappers import RateLimitedLLMClient, RateLimiter


class StubClient(LLMClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def generate_json(self, *, prompt: str, user_input: str) -> dict:
        self.calls.append((prompt, user_input))
        return {"ok": True}


def test_rate_limited_llm_client_delegates() -> None:
    wrapped = StubClient()
    client = RateLimitedLLMClient(wrapped, rate_limiter=RateLimiter(max_rpm=60000))

    result = client.generate_json(prompt="p", user_input="u")

    assert result == {"ok": True}
    assert wrapped.calls == [("p", "u")]
