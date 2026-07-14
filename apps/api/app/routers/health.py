"""Liveness/readiness endpoints and the Ollama model startup check."""

import logging

import httpx
import redis as redis_lib
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine
from app.services.storage import storage_healthy

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger("scopeguard.health")


class HealthStatus(BaseModel):
    status: str
    version: str = "0.1.0"


class DependencyStatus(BaseModel):
    database: bool
    redis: bool
    minio: bool
    ollama: bool
    celery: bool


class OllamaModelCheck(BaseModel):
    reachable: bool
    provider: str
    chat_model: str
    embed_model: str
    installed_models: list[str]
    missing_models: list[str]
    install_commands: list[str]
    message: str


@router.get("", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok")


def _db_healthy() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _redis_healthy() -> bool:
    try:
        client = redis_lib.Redis.from_url(
            get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        return bool(client.ping())
    except Exception:
        return False


def _ollama_healthy() -> bool:
    settings = get_settings()
    if settings.llm_provider == "fake":
        return True
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
        return response.status_code == 200
    except Exception:
        return False


def _celery_healthy() -> bool:
    try:
        from app.worker import celery_app

        replies = celery_app.control.inspect(timeout=2).ping()
        return bool(replies)
    except Exception:
        return False


@router.get("/ready", response_model=DependencyStatus)
def readiness() -> DependencyStatus:
    return DependencyStatus(
        database=_db_healthy(),
        redis=_redis_healthy(),
        minio=storage_healthy(),
        ollama=_ollama_healthy(),
        celery=_celery_healthy(),
    )


@router.get("/ollama", response_model=OllamaModelCheck)
def ollama_models() -> OllamaModelCheck:
    """Startup check: which configured models are missing and how to install them."""
    settings = get_settings()
    required = [settings.ollama_chat_model, settings.ollama_embed_model]

    if settings.llm_provider == "fake":
        return OllamaModelCheck(
            reachable=True,
            provider="fake",
            chat_model=settings.ollama_chat_model,
            embed_model=settings.ollama_embed_model,
            installed_models=[],
            missing_models=[],
            install_commands=[],
            message="LLM_PROVIDER=fake — no Ollama models are required in this mode.",
        )

    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        response.raise_for_status()
        installed = [m["name"] for m in response.json().get("models", [])]
    except Exception:
        return OllamaModelCheck(
            reachable=False,
            provider="ollama",
            chat_model=settings.ollama_chat_model,
            embed_model=settings.ollama_embed_model,
            installed_models=[],
            missing_models=required,
            install_commands=[f"ollama pull {m}" for m in required],
            message=(
                f"Ollama is not reachable at {settings.ollama_base_url}. Start it "
                "(e.g. `docker compose --profile ai up ollama` or `ollama serve`), then pull "
                "the models listed in install_commands. You can change models via "
                "OLLAMA_CHAT_MODEL / OLLAMA_EMBED_MODEL."
            ),
        )

    def _has(model: str) -> bool:
        return any(name == model or name.split(":")[0] == model for name in installed)

    missing = [m for m in required if not _has(m)]
    return OllamaModelCheck(
        reachable=True,
        provider="ollama",
        chat_model=settings.ollama_chat_model,
        embed_model=settings.ollama_embed_model,
        installed_models=installed,
        missing_models=missing,
        install_commands=[f"ollama pull {m}" for m in missing],
        message=(
            "All configured models are installed."
            if not missing
            else "Some models are missing. Run the install_commands, or set "
            "OLLAMA_CHAT_MODEL / OLLAMA_EMBED_MODEL to models you already have."
        ),
    )
