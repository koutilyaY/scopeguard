"""Structured JSON logging with request-ID support and sensitive-field redaction."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
org_id_var: ContextVar[str | None] = ContextVar("org_id", default=None)

# Keys whose values must never appear in logs.
REDACTED_KEYS = {
    "password",
    "hashed_password",
    "new_password",
    "current_password",
    "secret",
    "secret_key",
    "authorization",
    "cookie",
    "set-cookie",
    "session_token",
    "csrf_token",
    "extracted_text",
    "body",  # uploaded email bodies
}


def redact(value: Any) -> Any:
    """Recursively replace sensitive values so they never reach log output."""
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if k.lower() in REDACTED_KEYS else redact(v) for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if request_id_var.get():
            payload["request_id"] = request_id_var.get()
        if user_id_var.get():
            payload["user_id"] = user_id_var.get()
        if org_id_var.get():
            payload["organization_id"] = org_id_var.get()
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(redact(extra))
        return json.dumps(payload, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    # uvicorn access logs contain URLs only; keep them but route through JSON formatter
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def log_with(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    logger.log(level, message, extra={"extra_fields": fields})
