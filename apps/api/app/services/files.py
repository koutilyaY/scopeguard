"""Upload validation: MIME/extension allowlist, size limits, name sanitisation, hashing."""

import hashlib
import re
import unicodedata

from fastapi import HTTPException, status

from app.config import get_settings

# extension -> allowed MIME types the client may declare
ALLOWED_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    },
    ".csv": {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel"},
    ".txt": {"text/plain"},
    ".eml": {"message/rfc822", "text/plain", "application/octet-stream"},
}

# magic bytes for binary formats we accept
MAGIC = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",
    ".xlsx": b"PK\x03\x04",
}


def sanitize_filename(name: str) -> str:
    """Keep a safe display filename; storage keys are random and never user-derived."""
    name = unicodedata.normalize("NFKD", name)
    name = name.replace("\\", "/").split("/")[-1]  # strip any path components
    name = re.sub(r"[^\w.\- ]", "_", name)
    name = name.strip(" .")
    return name[:200] or "upload"


def get_extension(filename: str) -> str:
    lowered = sanitize_filename(filename).lower()
    for ext in ALLOWED_TYPES:
        if lowered.endswith(ext):
            return ext
    return ""


def validate_upload(filename: str, declared_mime: str, data: bytes) -> tuple[str, str]:
    """Validate an upload; returns (sanitized_name, extension) or raises 4xx."""
    settings = get_settings()
    if len(data) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="File is empty")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the maximum size of {settings.max_upload_bytes} bytes",
        )
    safe_name = sanitize_filename(filename)
    ext = get_extension(safe_name)
    if not ext:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )
    base_mime = (declared_mime or "").split(";")[0].strip().lower()
    if base_mime and base_mime not in ALLOWED_TYPES[ext]:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"MIME type '{base_mime}' does not match extension '{ext}'",
        )
    magic = MAGIC.get(ext)
    if magic and not data.startswith(magic):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File content does not look like a valid {ext} file",
        )
    return safe_name, ext


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
