"""Ollama provider. Timeouts, retries and context-size protection live here."""

import logging
import time

import httpx

from app.config import get_settings
from app.services.llm.base import LLMProvider, LLMUnavailableError, ModelMetadata

logger = logging.getLogger("scopeguard.llm.ollama")

# Rough context protection: refuse prompts beyond this many characters so a huge
# document cannot silently truncate mid-clause. Callers chunk long inputs instead.
MAX_PROMPT_CHARS = 48_000
TRANSIENT_RETRIES = 2


class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__()
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.chat_model = settings.ollama_chat_model
        self.embed_model = settings.ollama_embed_model
        self.timeout = settings.ollama_timeout_seconds

    def _generate_text(self, system_prompt: str, user_prompt: str) -> str:
        if len(system_prompt) + len(user_prompt) > MAX_PROMPT_CHARS:
            raise LLMUnavailableError(
                f"Prompt exceeds the {MAX_PROMPT_CHARS}-character context guard; "
                "input must be chunked before calling the model."
            )
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        last_exc: Exception | None = None
        for attempt in range(TRANSIENT_RETRIES + 1):
            try:
                response = httpx.post(
                    f"{self.base_url}/api/chat", json=payload, timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()["message"]["content"]
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                logger.warning("Ollama call failed (attempt %d): %s", attempt + 1, exc)
                time.sleep(min(2**attempt, 5))
        raise LLMUnavailableError(f"Ollama unreachable or failing at {self.base_url}: {last_exc}")

    def create_embeddings(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            try:
                response = httpx.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.embed_model, "input": text[:8000]},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                vectors.append(response.json()["embeddings"][0])
            except (httpx.TransportError, httpx.HTTPStatusError, KeyError) as exc:
                raise LLMUnavailableError(f"Embedding call failed: {exc}") from exc
        return vectors

    def health_check(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except httpx.TransportError:
            return False

    def model_metadata(self) -> ModelMetadata:
        return ModelMetadata(
            provider="ollama", chat_model=self.chat_model, embed_model=self.embed_model
        )
