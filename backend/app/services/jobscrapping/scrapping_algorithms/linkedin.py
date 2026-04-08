"""
LinkedIn job discovery (best-effort guest HTML). Prefer official/partner APIs in production.

Wired from :mod:`backend.app.services.jobscrapping.unified_ingest`; see ``third_party_job_feeds``.
"""
from __future__ import annotations

from typing import Any

from .third_party_job_feeds import fetch_linkedin_guest_raw_jobs


def is_available() -> bool:
    return True


def describe() -> dict[str, Any]:
    return {
        "portal": "linkedin",
        "status": "best_effort_guest_html",
        "note": "Uses jobs-guest HTML; fragile. Respect LinkedIn ToS and rate limits.",
    }


def fetch_for_company(company: str, *, timeout_sec: float = 25):
    """Return ``(list[RawJob], failures)`` for unified ingest."""
    return fetch_linkedin_guest_raw_jobs(company, timeout_sec=timeout_sec)
