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
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

if TYPE_CHECKING:
    from backend.app.services.company_search.base import JobResult


_WS = re.compile(r"\s+")
_TITLE_SUFFIXES = (
    r"\s*[-|]\s*jobs?$",
    r"\s*[-|]\s*careers?$",
    r"\s*[-|]\s*greenhouse$",
    r"\s*[-|]\s*lever$",
    r"\s*[-|]\s*ashby$",
)
_TRACKING_QUERY_KEYS = {
    "gh_src",
    "source",
    "ref",
    "referer",
    "lang",
    "locale",
    "lever-source",
}


def norm(s: str | None) -> str:
    if s is None:
        return ""
    t = str(s).strip().lower()
    return _WS.sub(" ", t)


def _normalize_title_for_hash(title: str | None) -> str:
    t = norm(title)
    if not t:
        return ""
    for pattern in _TITLE_SUFFIXES:
        t = re.sub(pattern, "", t, flags=re.IGNORECASE)
    return _WS.sub(" ", t).strip()


def canonicalize_job_url(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        p = urlparse(raw)
        if not p.scheme or not p.netloc:
            return raw

        path = (p.path or "/").rstrip("/") or "/"
        host = (p.netloc or "").lower()

        # Ashby often serves both ".../<jobId>" and ".../<jobId>/application".
        if "ashbyhq.com" in host and path.endswith("/application"):
            path = path[: -len("/application")] or "/"

        query_items = []
        for k, v in parse_qsl(p.query, keep_blank_values=True):
            key = (k or "").lower()
            if key in _TRACKING_QUERY_KEYS or key.startswith("utm_"):
                continue
            query_items.append((k, v))
        query = urlencode(query_items, doseq=True)
        return urlunparse((p.scheme.lower(), host, path, p.params, query, ""))
    except Exception:
        return raw


def _extract_ats_identity(canonical_url: str) -> tuple[str | None, str | None]:
    try:
        p = urlparse(canonical_url)
        host = (p.netloc or "").lower()
        parts = [seg for seg in (p.path or "").split("/") if seg]

        if "ashbyhq.com" in host and len(parts) >= 2:
            platform = "ashby"
            company_slug = parts[0].lower()
            job_id = parts[1].lower()
            if job_id == "application" and len(parts) >= 3:
                job_id = parts[2].lower()
            return platform, f"{company_slug}:{job_id}"

        if "lever.co" in host and len(parts) >= 2:
            platform = "lever"
            company_slug = parts[0].lower()
            job_id = parts[1].lower()
            return platform, f"{company_slug}:{job_id}"

        if "greenhouse.io" in host:
            platform = "greenhouse"
            lower_parts = [s.lower() for s in parts]
            if "jobs" in lower_parts:
                idx = lower_parts.index("jobs")
                if idx + 1 < len(parts):
                    board_slug = parts[idx - 1].lower() if idx > 0 else "board"
                    return platform, f"{board_slug}:{parts[idx + 1].lower()}"

        if "rippling.com" in host:
            platform = "rippling"
            lower_parts = [s.lower() for s in parts]
            for marker in ("jobs", "job"):
                if marker in lower_parts:
                    idx = lower_parts.index(marker)
                    if idx + 1 < len(parts):
                        return platform, parts[idx + 1].lower()

        return None, None
    except Exception:
        return None, None


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
    canonical_url = canonicalize_job_url(url)
    platform, stable_id = _extract_ats_identity(canonical_url)
    if platform and stable_id:
        payload = f"{platform}|{stable_id}|{norm(company)}"
    else:
        payload = f"{_normalize_title_for_hash(title)}|{norm(company)}|{norm(canonical_url)}"
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
        url=canonicalize_job_url(raw.url),
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
