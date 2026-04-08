"""
Naukri job discovery (best-effort search HTML). Prefer official/partner feeds when available.

Wired from :mod:`backend.app.services.jobscrapping.unified_ingest`; see ``third_party_job_feeds``.
"""
from __future__ import annotations

from typing import Any

from .third_party_job_feeds import fetch_naukri_search_raw_jobs


def is_available() -> bool:
    return True


def describe() -> dict[str, Any]:
    return {
        "portal": "naukri",
        "status": "best_effort_search_html",
        "note": "Parses naukri.com search results; may break on markup changes.",
    }


def fetch_for_company(company: str, *, timeout_sec: float = 25):
    return fetch_naukri_search_raw_jobs(company, timeout_sec=timeout_sec)
