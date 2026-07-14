"""LLM provider factory."""

from app.config import get_settings
from app.services.llm.base import (
    LLMError,
    LLMOutputError,
    LLMProvider,
    LLMUnavailableError,
)
from app.services.llm.fake import FakeLLMProvider
from app.services.llm.ollama import OllamaProvider

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        if get_settings().llm_provider == "fake":
            _provider = FakeLLMProvider()
        else:
            _provider = OllamaProvider()
    return _provider


def set_llm_provider(provider: LLMProvider | None) -> None:
    """Dependency injection hook for tests."""
    global _provider
    _provider = provider


__all__ = [
    "FakeLLMProvider",
    "LLMError",
    "LLMOutputError",
    "LLMProvider",
    "LLMUnavailableError",
    "OllamaProvider",
    "get_llm_provider",
    "set_llm_provider",
]
