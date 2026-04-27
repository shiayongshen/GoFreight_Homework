from dc_nl_cli.config import Settings
from dc_nl_cli.llm.factory import build_llm_client
from dc_nl_cli.llm.gemini import GeminiClient
from dc_nl_cli.llm.ollama import OllamaClient
from dc_nl_cli.llm.openai_compatible import (
    OpenAICompatibleClient,
    OpenAIResponsesClient,
)


def test_llm_factory_builds_gemini_client() -> None:
    client = build_llm_client(
        Settings(
            llm_provider="gemini",
            llm_model="gemini-2.5-flash",
            gemini_api_key="test-key",
        )
    )
    assert isinstance(client, GeminiClient)


def test_llm_factory_builds_openai_client() -> None:
    client = build_llm_client(
        Settings(
            llm_provider="openai",
            llm_model="gpt-4.1-mini",
            openai_api_key="test-key",
        )
    )
    assert isinstance(client, OpenAIResponsesClient)


def test_llm_factory_builds_groq_client() -> None:
    client = build_llm_client(
        Settings(
            llm_provider="groq",
            llm_model="llama-3.3-70b-versatile",
            groq_api_key="test-key",
        )
    )
    assert isinstance(client, OpenAICompatibleClient)


def test_llm_factory_builds_ollama_client() -> None:
    client = build_llm_client(
        Settings(
            llm_provider="ollama",
            llm_model="gemma4:e2b",
        )
    )
    assert isinstance(client, OllamaClient)


def test_llm_factory_returns_none_when_api_key_missing() -> None:
    client = build_llm_client(Settings(llm_provider="openai", llm_model="gpt-4.1-mini"))
    assert client is None
