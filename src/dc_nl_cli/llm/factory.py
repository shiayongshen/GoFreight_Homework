from __future__ import annotations

from dc_nl_cli.config import Settings
from dc_nl_cli.errors import ConfigurationError
from dc_nl_cli.llm.base import LLMClient
from dc_nl_cli.llm.gemini import GeminiClient
from dc_nl_cli.llm.ollama import OllamaClient
from dc_nl_cli.llm.openai_compatible import (
    OpenAICompatibleClient,
    OpenAIResponsesClient,
)


def build_llm_client(settings: Settings) -> LLMClient | None:
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        if not settings.gemini_api_key:
            return None
        return GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.llm_model,
            base_url=settings.gemini_base_url,
            timeout=settings.request_timeout_seconds,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            return None
        return OpenAIResponsesClient(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
            base_url=settings.openai_base_url,
            timeout=settings.request_timeout_seconds,
        )

    if provider == "groq":
        if not settings.groq_api_key:
            return None
        return OpenAICompatibleClient(
            api_key=settings.groq_api_key,
            model=settings.llm_model,
            base_url=settings.groq_base_url,
            timeout=settings.request_timeout_seconds,
        )

    if provider == "ollama":
        return OllamaClient(
            api_key=settings.ollama_api_key,
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
            timeout=settings.request_timeout_seconds,
        )

    raise ConfigurationError(f"unsupported LLM provider: {settings.llm_provider}")
