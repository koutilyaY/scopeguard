"""LLM provider interface. Domain logic depends on this, never on raw HTTP calls."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base error for provider failures (unreachable, timeout, malformed output)."""


class LLMUnavailableError(LLMError):
    pass


class LLMOutputError(LLMError):
    """Model returned output that failed schema validation after retries."""


@dataclass
class ModelMetadata:
    provider: str
    chat_model: str
    embed_model: str


@dataclass
class UsageMetrics:
    prompt_chars: int = 0
    completion_chars: int = 0
    calls: int = 0

    def record(self, prompt: str, completion: str) -> None:
        self.calls += 1
        self.prompt_chars += len(prompt)
        self.completion_chars += len(completion)


@dataclass
class GenerationResult:
    parsed: BaseModel
    raw_text: str
    attempts: int


class LLMProvider(ABC):
    """generate_structured / create_embeddings / health_check / model_metadata."""

    def __init__(self) -> None:
        self.usage = UsageMetrics()

    @abstractmethod
    def _generate_text(self, system_prompt: str, user_prompt: str) -> str:
        """Single raw completion call."""

    @abstractmethod
    def create_embeddings(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def health_check(self) -> bool: ...

    @abstractmethod
    def model_metadata(self) -> ModelMetadata: ...

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        max_attempts: int = 3,
    ) -> tuple[T, GenerationResult]:
        """Generate JSON matching `schema`, with retry-and-repair on malformed output."""
        last_error: Exception | None = None
        prompt = user_prompt
        for attempt in range(1, max_attempts + 1):
            raw = self._generate_text(system_prompt, prompt)
            self.usage.record(system_prompt + prompt, raw)
            try:
                data = extract_json(raw)
                parsed = schema.model_validate(data)
                return parsed, GenerationResult(parsed=parsed, raw_text=raw, attempts=attempt)
            except (ValueError, ValidationError) as exc:
                last_error = exc
                # repair loop: tell the model what was wrong, ask for corrected JSON only
                prompt = (
                    f"{user_prompt}\n\nYour previous response could not be parsed against the "
                    f"required JSON schema. Error: {exc}\nRespond again with ONLY valid JSON "
                    "matching the schema — no prose, no markdown fences."
                )
        raise LLMOutputError(
            f"Model output failed validation after {max_attempts} attempts: {last_error}"
        )


def extract_json(text: str) -> dict | list:
    """Pull a JSON object out of model output that may include fences or prose."""
    text = text.strip()
    # strip <think>...</think> blocks some local models emit
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # fall back to the outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("No JSON object found in model output")
