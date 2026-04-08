"""
Live HTTP/JSON public URL feeds: adapter layer maps provider payloads to `RawJob`.

Timeouts and retries come from merged `settings` (`http_timeout_sec`, `retries`).

Paired with :mod:`company_careers` under ``scrapping_algorithms``. Future portal feeds
(LinkedIn, Naukri) will live in dedicated modules and plug into the same ingest pipeline.
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from backend.app.services.jobscrapping.normalize import RawJob

logger = logging.getLogger(__name__)

_PREFIX = "[ingest:public-urls]"


def log_json(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, default=str))


class FeedAdapter(ABC):
    @abstractmethod
    def to_raw_jobs(self, payload: Any, *, feed_name: str) -> list[RawJob]:
        ...


class RemotiveAdapter(FeedAdapter):
    """https://remotive.com/api/remote-jobs — `jobs` array."""

    def to_raw_jobs(self, payload: Any, *, feed_name: str) -> list[RawJob]:
        if not isinstance(payload, dict):
            return []
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            return []
        out: list[RawJob] = []
        for item in jobs:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            company = (item.get("company_name") or item.get("company") or "").strip() or "Unknown"
            if not title or not url:
                continue
            loc = (item.get("candidate_required_location") or item.get("job_type") or "") or None
            remote = "remote" in str(item.get("job_type", "")).lower() or (
                loc and "remote" in str(loc).lower()
            )
            out.append(
                RawJob(
                    title=title,
                    company=company,
                    url=url,
                    location=str(loc).strip() if loc else None,
                    description=(item.get("description") or "")[:8000] or None,
                    remote=bool(remote),
                    extra={"feed": feed_name, "adapter": "remotive"},
                )
            )
        return out


class GenericJsonAdapter(FeedAdapter):
    """
    Best-effort: find a top-level or nested list of objects with title + url;
    company from `company`, `company_name`, or employer name.
    """

    def to_raw_jobs(self, payload: Any, *, feed_name: str) -> list[RawJob]:
        candidates = self._find_job_lists(payload)
        out: list[RawJob] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or item.get("name") or item.get("position") or "").strip()
            url = (item.get("url") or item.get("apply_url") or item.get("link") or "").strip()
            company = (
                item.get("company")
                or item.get("company_name")
                or item.get("employer")
                or item.get("organization")
                or "Unknown"
            )
            if isinstance(company, dict):
                company = str(company.get("name") or "Unknown")
            company = str(company).strip() or "Unknown"
            if not title or not url:
                continue
            loc = item.get("location") or item.get("candidate_required_location")
            if isinstance(loc, dict):
                loc = loc.get("name")
            out.append(
                RawJob(
                    title=title,
                    company=company,
                    url=url,
                    location=str(loc).strip() if loc else None,
                    description=None,
                    remote="remote" in str(item).lower(),
                    extra={"feed": feed_name, "adapter": "generic_json"},
                )
            )
        return out

    def _find_job_lists(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("jobs", "data", "results", "items", "listings", "positions"):
            v = payload.get(key)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        # shallow search
        for v in payload.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                if any(k in v[0] for k in ("title", "url", "apply_url")):
                    return v
        return []


def select_adapter(entry: dict[str, Any]) -> FeedAdapter:
    url = (entry.get("url") or "").lower()
    fmt = (entry.get("format") or entry.get("kind") or "").strip().lower()
    if "remotive.com" in url or fmt == "remotive":
        return RemotiveAdapter()
    return GenericJsonAdapter()


def _fetch_json_with_retries(
    url: str,
    *,
    timeout_sec: float,
    retries: int,
    headers: dict[str, str],
) -> Any:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout_sec, headers=headers)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            if attempt < retries:
                time.sleep(0.35 * (2**attempt))
    raise last if last else RuntimeError("fetch failed")


def fetch_all_public_feeds(
    merged_config: dict[str, Any],
) -> tuple[list[RawJob], list[dict[str, Any]]]:
    """
    Fetch enabled public URL feeds and map to RawJob. Returns (raw_jobs, failures).
    """
    settings = merged_config.get("settings") or {}
    timeout_sec = float(settings.get("http_timeout_sec") or 30)
    retries = max(0, int(settings.get("retries") or 3))
    feeds = merged_config.get("public_urls") or []

    enabled_feeds = [
        e for e in feeds if isinstance(e, dict) and e.get("enabled", True) is not False
    ]
    logger.info(
        "%s === run | feeds=%d | http_timeout_sec=%.1f | retries=%d ===",
        _PREFIX,
        len(enabled_feeds),
        timeout_sec,
        retries,
    )

    raw_jobs: list[RawJob] = []
    failures: list[dict[str, Any]] = []
    headers = {
        "User-Agent": "HireMate-Ingest/1.0 (+https://github.com)",
        "Accept": "application/json,text/plain,*/*",
    }

    for entry in feeds:
        if not isinstance(entry, dict):
            continue
        if entry.get("enabled", True) is False:
            continue
        name = (entry.get("name") or "feed").strip()
        url = (entry.get("url") or "").strip()
        if not url:
            failures.append(
                {"kind": "public_feed", "target": name, "message": "missing_url"}
            )
            continue
        adapter = select_adapter(entry)
        logger.info(
            "%s fetching | feed=%s | adapter=%s | url=%s",
            _PREFIX,
            name,
            adapter.__class__.__name__,
            url,
        )
        t0 = time.monotonic()
        try:
            payload = _fetch_json_with_retries(
                url, timeout_sec=timeout_sec, retries=retries, headers=headers
            )
            jobs = adapter.to_raw_jobs(payload, feed_name=name)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            raw_jobs.extend(jobs)
            logger.info(
                "%s done | feed=%s | jobs_mapped=%d | elapsed_ms=%d",
                _PREFIX,
                name,
                len(jobs),
                elapsed_ms,
            )
            log_json(
                "public_feed_done",
                feed=name,
                url=url,
                adapter=adapter.__class__.__name__,
                jobs_seen=len(jobs),
                elapsed_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "%s FAILED | feed=%s | elapsed_ms=%d | error=%s",
                _PREFIX,
                name,
                elapsed_ms,
                e,
            )
            log_json(
                "public_feed_error",
                feed=name,
                url=url,
                adapter=adapter.__class__.__name__,
                error=str(e),
                elapsed_ms=elapsed_ms,
            )
            failures.append(
                {
                    "kind": "public_feed",
                    "target": name,
                    "url": url,
                    "message": str(e),
                }
            )

    logger.info(
        "%s === finished | total_raw_jobs=%d | feed_failures=%d ===",
        _PREFIX,
        len(raw_jobs),
        len(failures),
    )
    return raw_jobs, failures
