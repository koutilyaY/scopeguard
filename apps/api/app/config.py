"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    secret_key: str = "dev-only-secret-key-change-in-production"

    database_url: str = (
        "postgresql+psycopg://scopeguard:scopeguard-dev-password@localhost:5433/scopeguard"
    )
    redis_url: str = "redis://localhost:6380/0"
    celery_broker_url: str = "redis://localhost:6380/1"
    celery_result_backend: str = "redis://localhost:6380/2"

    minio_endpoint: str = "localhost:9002"
    minio_access_key: str = "scopeguard"
    minio_secret_key: str = "scopeguard-dev-secret"
    minio_bucket: str = "scopeguard-documents"
    minio_secure: bool = False

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3:8b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_embed_dimensions: int = 768
    ollama_timeout_seconds: int = 120
    llm_provider: str = "ollama"  # "ollama" | "fake"

    session_ttl_minutes: int = 480
    session_cookie_name: str = "scopeguard_session"
    csrf_cookie_name: str = "scopeguard_csrf"
    cookie_secure: bool = False
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    password_min_length: int = 12
    cors_origins: str = "http://localhost:3000"

    max_upload_bytes: int = 25 * 1024 * 1024

    smtp_host: str = "localhost"
    smtp_port: int = 1025

    # Prompt / model bookkeeping
    prompt_dir: str = "prompts"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
