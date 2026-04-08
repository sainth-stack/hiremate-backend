"""
Per-route ingest lock using Redis (optional). Fail-open if Redis is unavailable.

Uses the sync Redis client from ``app.utils.cache`` when ``redis_url`` is set.
"""
from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from fastapi import HTTPException, status

from backend.app.core.config import settings
from backend.app.utils.cache import _get_sync_redis

logger = logging.getLogger(__name__)

_INGEST_LOCK_PREFIX = "ingest:lock:"


def clear_stale_ingest_locks_on_startup() -> None:
    """
    Remove Redis keys matching ``ingest:lock:*`` when the app process starts.

    If the server was killed while an ingest held the lock, the key could remain
    for up to ``ingest_lock_ttl_sec`` without this. Disabled when
    ``ingest_clear_locks_on_startup`` is false (e.g. multi-instance ingest).
    """
    if not settings.ingest_redis_lock_enabled or not settings.ingest_clear_locks_on_startup:
        return
    r = _get_sync_redis()
    if not r:
        return
    try:
        keys = list(r.scan_iter(f"{_INGEST_LOCK_PREFIX}*", count=32))
        if not keys:
            return
        deleted = r.delete(*keys)
        logger.info(
            "Cleared %d stale ingest lock key(s) from Redis (restart after crash/kill)",
            deleted,
        )
    except Exception as e:
        logger.warning("Could not clear ingest lock keys on startup: %s", e)


@contextmanager
def ingest_route_lock(route_key: str) -> Generator[None, None, None]:
    """
    Acquire a non-blocking lock for ``ingest:{route_key}``. Yields if acquired or if
    locking is disabled / Redis unavailable. Raises 409 if another ingest holds the lock.
    """
    if not settings.ingest_redis_lock_enabled:
        yield
        return
    r = _get_sync_redis()
    if not r:
        yield
        return
    try:
        from redis.lock import Lock
    except ImportError:
        yield
        return

    ttl = max(60, int(getattr(settings, "ingest_lock_ttl_sec", 1800)))
    lock = Lock(r, f"{_INGEST_LOCK_PREFIX}{route_key}", timeout=ttl)
    acquired = lock.acquire(blocking=False)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ingest already running for {route_key}. Retry later.",
        )
    try:
        yield
    finally:
        try:
            lock.release()
        except Exception as e:
            logger.debug("ingest lock release: %s", e)
