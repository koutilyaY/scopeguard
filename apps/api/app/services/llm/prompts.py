"""Versioned prompt loading. The active version is recorded on every ReviewRun
and GeneratedArtifact so results are reproducible."""

from functools import lru_cache
from pathlib import Path

PROMPT_VERSION = "v1"
_PROMPT_DIR = Path(__file__).resolve().parents[3] / "prompts"

PROMPT_FILES = {
    "contract_extraction": f"contract_extraction_{PROMPT_VERSION}.txt",
    "scope_classification": f"scope_classification_{PROMPT_VERSION}.txt",
    "artifact_draft": f"artifact_draft_{PROMPT_VERSION}.txt",
}


@lru_cache
def load_prompt(name: str) -> str:
    filename = PROMPT_FILES.get(name)
    if filename is None:
        raise KeyError(f"Unknown prompt '{name}'")
    return (_PROMPT_DIR / filename).read_text()
