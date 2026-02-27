"""
Cache for keyword analysis results.
In-memory LRU + TTL for now. Redis migration: replace get/set with redis.get/setex;
same key (hash) and value (result dict) contract.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

_cache: OrderedDict[str, tuple[dict[str, Any], float]] = OrderedDict()
_lock = threading.Lock()


def get(key: str) -> Optional[dict[str, Any]]:
    """Get cached analysis result. Returns None on miss or expiry."""
    with _lock:
        if key not in _cache:
            return None
        val, expiry = _cache[key]
        if time.time() > expiry:
            del _cache[key]
            return None
        _cache.move_to_end(key)
        return val


def set(key: str, value: dict[str, Any]) -> None:
    """Cache analysis result with TTL. Evicts LRU when at capacity."""
    with _lock:
        while len(_cache) >= settings.analysis_cache_max_entries and _cache:
            _cache.popitem(last=False)
        _cache[key] = (value, time.time() + settings.analysis_cache_ttl)
        _cache.move_to_end(key)
    logger.debug("Analysis cached key=%s entries=%d", key[:16], len(_cache))


def clear() -> None:
    """Clear all entries (for tests / Redis migration)."""
    with _lock:
        _cache.clear()
