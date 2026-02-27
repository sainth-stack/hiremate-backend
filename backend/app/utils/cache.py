"""
Redis cache utility - used for dashboard summary, autofill context.
If Redis unavailable, caching is disabled and all ops no-op.
"""
import json
import logging
from typing import Any

from backend.app.core.config import settings

logger = logging.getLogger(__name__)
_client = None


async def connect() -> None:
    global _client
    url = settings.redis_url
    if not url:
        logger.warning("redis_url not set — caching disabled")
        return
    try:
        from redis import asyncio as aioredis
        _client = aioredis.Redis.from_url(
            url, encoding="utf-8", decode_responses=True
        )
        await _client.ping()
        logger.info("Redis connected — caching enabled")
    except Exception as e:
        logger.warning("Redis connect failed: %s — caching disabled", e)


async def get(key: str) -> Any:
    if not _client:
        return None
    try:
        val = await _client.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


async def set(key: str, value: Any, ttl: int | None = None) -> None:
    if not _client:
        return
    ttl_val = ttl if ttl is not None else settings.autofill_context_cache_ttl
    try:
        await _client.set(key, json.dumps(value), ex=ttl_val)
    except Exception:
        pass


async def delete(key: str) -> None:
    if not _client:
        return
    try:
        await _client.delete(key)
    except Exception:
        pass
