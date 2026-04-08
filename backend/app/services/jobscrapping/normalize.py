"""
Normalize raw scraped rows into DB-ready payloads and content_hash.

content_hash = SHA256(norm(title) + "|" + norm(company) + "|" + norm(url))

Note: the same requisition may appear under different URLs (tracking params, ATS mirrors),
producing multiple rows. Secondary dedup is a later improvement (plan.md).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.app.services.company_search.base import JobResult


_WS = re.compile(r"\s+")


def norm(s: str | None) -> str:
    if s is None:
        return ""
    t = str(s).strip().lower()
    return _WS.sub(" ", t)


@dataclass
class RawJob:
    """Scraper-neutral input before persistence."""

    title: str
    company: str
    url: str
    location: str | None = None
    description: str | None = None
    remote: bool = False
    salary_min: int | None = None
    salary_max: int | None = None
    posted_at: datetime | None = None
    extra: dict[str, Any] | None = None


@dataclass
class JobCreate:
    """Row ready for `jobs` table upsert."""

    title: str
    company: str
    url: str
    location: str | None
    description: str | None
    remote: bool
    salary_min: int | None
    salary_max: int | None
    posted_at: datetime | None
    source: str
    source_detail: dict[str, Any] | None
    content_hash: str


def compute_content_hash(title: str, company: str, url: str) -> str:
    payload = f"{norm(title)}|{norm(company)}|{norm(url)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def job_result_to_raw_job(
    jr: "JobResult",
    *,
    company_display: str | None = None,
) -> RawJob:
    """Map company search `JobResult` into ingestion `RawJob`."""
    loc = jr.location
    remote = bool(loc and "remote" in str(loc).lower())
    return RawJob(
        title=jr.role,
        company=(company_display or jr.company).strip(),
        url=jr.apply_url,
        location=loc,
        description=jr.description,
        remote=remote,
        posted_at=jr.posted_at,
    )


def raw_to_job_create(
    raw: RawJob,
    *,
    source: str,
    source_detail: dict[str, Any] | None = None,
) -> JobCreate:
    h = compute_content_hash(raw.title, raw.company, raw.url)
    detail = dict(source_detail or {})
    if raw.extra:
        detail = {**detail, **raw.extra}
    return JobCreate(
        title=raw.title.strip(),
        company=raw.company.strip(),
        url=str(raw.url).strip(),
        location=raw.location.strip() if raw.location else None,
        description=raw.description,
        remote=bool(raw.remote),
        salary_min=raw.salary_min,
        salary_max=raw.salary_max,
        posted_at=raw.posted_at,
        source=source,
        source_detail=detail if detail else None,
        content_hash=h,
    )
