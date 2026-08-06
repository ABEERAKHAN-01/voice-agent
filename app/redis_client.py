"""
Redis client used as a cache-aside layer in front of Postgres for:
  - GET /patients/:id
  - phone-number duplicate lookups (hot path during live calls)
Cache is best-effort: any Redis failure degrades to a DB read, it never
breaks the request.
"""
import json
from typing import Any

import redis.asyncio as redis
import structlog

from app.config import settings

log = structlog.get_logger()

redis_client: redis.Redis = redis.from_url(
    settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2
)


async def cache_get(key: str) -> Any | None:
    try:
        raw = await redis_client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001
        log.warning("cache_get_failed", key=key, error=str(exc))
        return None


async def cache_set(key: str, value: Any, ttl: int = settings.CACHE_TTL_SECONDS) -> None:
    try:
        await redis_client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as exc:  # noqa: BLE001
        log.warning("cache_set_failed", key=key, error=str(exc))


async def cache_delete(*keys: str) -> None:
    try:
        if keys:
            await redis_client.delete(*keys)
    except Exception as exc:  # noqa: BLE001
        log.warning("cache_delete_failed", keys=keys, error=str(exc))
