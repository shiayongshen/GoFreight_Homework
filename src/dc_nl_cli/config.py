from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


DEFAULT_DC_API_KEY = "AIzaSyCTI4Xz-UW_G2Q2RfknhcfdAnTHq5X5XuI"
DEFAULT_DC_BASE_URL = "https://api.datacommons.org/v2"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/api"


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"
    resolver_mode: str = "api"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    ollama_api_key: str | None = None
    datacommons_api_key: str = DEFAULT_DC_API_KEY
    datacommons_base_url: str = DEFAULT_DC_BASE_URL
    gemini_base_url: str = DEFAULT_GEMINI_BASE_URL
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL
    groq_base_url: str = DEFAULT_GROQ_BASE_URL
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    request_timeout_seconds: float = 30.0


def load_settings() -> Settings:
    load_dotenv()
    timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "gemini"),
        llm_model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
        resolver_mode=os.getenv("RESOLVER_MODE", "api"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        ollama_api_key=os.getenv("OLLAMA_API_KEY"),
        datacommons_api_key=os.getenv("DATACOMMONS_API_KEY", DEFAULT_DC_API_KEY),
        datacommons_base_url=os.getenv("DATACOMMONS_BASE_URL", DEFAULT_DC_BASE_URL),
        gemini_base_url=os.getenv("GEMINI_BASE_URL", DEFAULT_GEMINI_BASE_URL),
        openai_base_url=os.getenv("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
        groq_base_url=os.getenv("GROQ_BASE_URL", DEFAULT_GROQ_BASE_URL),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        request_timeout_seconds=timeout,
    )
