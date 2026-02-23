"""
Short-lived storage for Tailor Resume context from extension.
When user clicks "Tailor Resume" on a job page, we store JD + title; resume-generator fetches and clears.
"""
from __future__ import annotations

import time
from typing import Any

_TTL_SEC = 300
_store: dict[int, tuple[float, dict[str, Any]]] = {}


def set_tailor_context(user_id: int, job_description: str, job_title: str = "", url: str = "") -> None:
    _store[user_id] = (time.time(), {
        "job_description": job_description or "",
        "job_title": job_title or "",
        "url": url or "",
    })


def get_and_clear_tailor_context(user_id: int) -> dict[str, Any] | None:
    entry = _store.pop(user_id, None)
    if not entry:
        return None
    ts, ctx = entry
    if time.time() - ts > _TTL_SEC:
        return None
    return ctx
