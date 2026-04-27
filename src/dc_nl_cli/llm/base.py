from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate_json(self, *, prompt: str, user_input: str) -> dict:
        raise NotImplementedError
