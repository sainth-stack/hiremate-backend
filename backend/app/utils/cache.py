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
_sync_client = None

SHARED_FP_CACHE_TTL = 3600  # 1h for hits
SHARED_FP_MISS_TTL = 300  # 5min for negative cache


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


def _get_sync_redis():
    """Sync Redis client for Layer 3 SharedFieldProfileKey cache. Returns None if unavailable."""
    global _sync_client
    if _sync_client is False:
        return None
    if _sync_client is not None:
        return _sync_client
    if not settings.redis_url:
        _sync_client = False
        return None
    try:
        import redis
        _sync_client = redis.Redis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
        _sync_client.ping()
        return _sync_client
    except Exception as e:
        logger.warning("Sync Redis connect failed: %s — Layer 3 cache disabled", e)
        _sync_client = False
        return None


def get_shared_profile_keys_cached(fps: list[str], db) -> dict[str, str]:
    """Returns {fp: profile_key} for fps in SharedFieldProfileKey. Uses Redis when available."""
    from backend.app.models.form_field_learning import SharedFieldProfileKey

    if not fps:
        return {}
    r = _get_sync_redis()
    out = {}
    missing = []

    if r:
        try:
            pipe = r.pipeline()
            for fp in fps:
                pipe.get(f"sfpk:{fp}")
            results = pipe.execute()
            for fp, val in zip(fps, results):
                if val is not None:
                    if val != "__MISS__":
                        out[fp] = val
                else:
                    missing.append(fp)
        except Exception:
            missing = fps
            out = {}
    else:
        missing = fps

    if missing:
        rows = db.query(SharedFieldProfileKey).filter(
            SharedFieldProfileKey.field_fp.in_(missing)
        ).all()
        for row in rows:
            out[row.field_fp] = row.profile_key
        found_fps = {row.field_fp for row in rows}
        if r:
            try:
                pipe = r.pipeline()
                for row in rows:
                    pipe.setex(f"sfpk:{row.field_fp}", SHARED_FP_CACHE_TTL, row.profile_key)
                for fp in missing:
                    if fp not in found_fps:
                        pipe.setex(f"sfpk:{fp}", SHARED_FP_MISS_TTL, "__MISS__")
                pipe.execute()
            except Exception:
                pass
    return out
