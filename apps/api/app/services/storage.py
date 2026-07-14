"""MinIO object storage wrapper."""

import io
import secrets

from minio import Minio

from app.config import get_settings

_client: Minio | None = None


def get_minio() -> Minio:
    global _client
    if _client is None:
        s = get_settings()
        _client = Minio(
            s.minio_endpoint,
            access_key=s.minio_access_key,
            secret_key=s.minio_secret_key,
            secure=s.minio_secure,
        )
    return _client


def reset_minio() -> None:
    global _client
    _client = None


def ensure_bucket() -> None:
    client = get_minio()
    bucket = get_settings().minio_bucket
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def generate_storage_key(organization_id: str, extension: str) -> str:
    """Random, non-user-controlled object key; prevents path traversal by construction."""
    return f"{organization_id}/{secrets.token_hex(16)}{extension}"


def put_object(storage_key: str, data: bytes, content_type: str) -> None:
    ensure_bucket()
    get_minio().put_object(
        get_settings().minio_bucket,
        storage_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def get_object(storage_key: str) -> bytes:
    response = get_minio().get_object(get_settings().minio_bucket, storage_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_object(storage_key: str) -> None:
    get_minio().remove_object(get_settings().minio_bucket, storage_key)


def storage_healthy() -> bool:
    try:
        get_minio().bucket_exists(get_settings().minio_bucket)
        return True
    except Exception:
        return False
