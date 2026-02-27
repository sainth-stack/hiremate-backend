"""
In-memory cache for job descriptions. Optimized for fast lookups with TTL and LRU eviction.

Usage: get(url), set(url, value). Swap backend to Redis later by changing this module.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from typing import Optional

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Key -> (value, expiry_timestamp) - OrderedDict maintains LRU order
_cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
_lock = asyncio.Lock()


def _cache_key(url: str) -> str:
    """Stable hash of URL for cache key (avoids storing very long URLs as dict keys)."""
    return hashlib.sha256(url.encode()).hexdigest()


async def get(url: str) -> Optional[str]:
    """Get cached job description if valid. Returns None on miss or expiry."""
    key = _cache_key(url)
    async with _lock:
        if key not in _cache:
            return None
        val, expiry = _cache[key]
        if time.monotonic() > expiry:
            del _cache[key]
            return None
        # LRU: move to end (most recently used)
        _cache.move_to_end(key)
        return val


async def set(url: str, job_description: str) -> None:
    """Cache job description with TTL. Evicts LRU entries when at capacity."""
    if not job_description or len(job_description) < 50:
        return
    key = _cache_key(url)
    async with _lock:
        # Evict oldest until we have room
        while len(_cache) >= settings.job_description_cache_max_entries and _cache:
            _cache.popitem(last=False)
        _cache[key] = (job_description, time.monotonic() + settings.job_description_cache_ttl)
        _cache.move_to_end(key)
    logger.debug("Cached job description url=%s len=%d entries=%d", url[:60], len(job_description), len(_cache))


async def delete(url: str) -> bool:
    """Remove from cache. Returns True if removed."""
    key = _cache_key(url)
    async with _lock:
        if key in _cache:
            del _cache[key]
            return True
        return False


def clear() -> None:
    """Clear all cached entries (for tests)."""
    _cache.clear()
