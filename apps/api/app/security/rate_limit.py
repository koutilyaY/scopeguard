"""Small fixed-window rate limiter backed by Redis, with in-memory fallback for tests."""

import time
from collections import defaultdict

import redis

from app.config import get_settings

_memory_buckets: dict[str, list[float]] = defaultdict(list)
_redis_client: redis.Redis | None = None
_redis_failed = False


def _get_redis() -> redis.Redis | None:
    global _redis_client, _redis_failed
    if _redis_failed:
        return None
    if _redis_client is None:
        try:
            _redis_client = redis.Redis.from_url(
                get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1
            )
            _redis_client.ping()
        except Exception:
            _redis_failed = True
            _redis_client = None
    return _redis_client


def check_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    client = _get_redis()
    if client is not None:
        try:
            bucket = f"ratelimit:{key}:{int(time.time()) // window_seconds}"
            count = int(client.incr(bucket))  # type: ignore[arg-type]
            if count == 1:
                client.expire(bucket, window_seconds + 1)
            return count <= limit
        except Exception:
            pass  # fall through to memory
    now = time.time()
    hits = _memory_buckets[key]
    _memory_buckets[key] = [t for t in hits if now - t < window_seconds]
    if len(_memory_buckets[key]) >= limit:
        return False
    _memory_buckets[key].append(now)
    return True


def reset_memory_limits() -> None:
    _memory_buckets.clear()
