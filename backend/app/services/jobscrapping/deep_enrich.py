"""
Optional deep enrich: fetch job detail pages for thin descriptions (first N URLs per run).

Uses ``job_detail_timeout_sec`` from merged settings (clamped 10–15s) with
``CareerPageScraper.fetch_job_description``. Skips network work when ``dry_run`` is True.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from backend.app.core.config import settings
from backend.app.services.company_search.career import CareerPageScraper
from backend.app.services.jobscrapping.normalize import RawJob

logger = logging.getLogger(__name__)

MIN_DESC_CHARS = 200


def log_json(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, default=str))


def _clamp_detail_timeout_sec(cfg: dict[str, Any]) -> int:
    raw = float(cfg.get("settings", {}).get("job_detail_timeout_sec") or 12)
    return int(max(10, min(15, raw)))


def _clamp_max_jobs(cfg: dict[str, Any]) -> int:
    raw = int(cfg.get("settings", {}).get("deep_enrich_max_jobs") or 20)
    return max(1, min(24, raw))


def deep_enrich_enabled(cfg: dict[str, Any]) -> bool:
    """Env ``INGEST_DEEP_ENRICH_ENABLED`` or YAML ``settings.deep_enrich_enabled``."""
    if settings.ingest_deep_enrich_enabled:
        return True
    s = cfg.get("settings") or {}
    return bool(s.get("deep_enrich_enabled"))


def enrich_raw_job_descriptions(
    cfg: dict[str, Any],
    jobs: list[RawJob],
    *,
    dry_run: bool,
) -> tuple[list[RawJob], dict[str, Any]]:
    """
    For the first ``deep_enrich_max_jobs`` rows that still need a richer description,
    fetch detail HTML. Returns (possibly mutated jobs list, stats dict).
    """
    if not deep_enrich_enabled(cfg) or dry_run:
        return jobs, {
            "deep_enrich_skipped": True,
            "reason": "disabled_or_dry_run",
            "deep_enrich_fetched": 0,
        }

    timeout_sec = _clamp_detail_timeout_sec(cfg)
    max_n = _clamp_max_jobs(cfg)
    scraper = CareerPageScraper(timeout_seconds=timeout_sec)

    need = [j for j in jobs if not j.description or len(j.description.strip()) < MIN_DESC_CHARS]
    slice_jobs = need[:max_n]
    fetched = 0
    for rj in slice_jobs:
        t0 = time.monotonic()
        try:
            text = scraper.fetch_job_description(rj.url)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            if text and len(text.strip()) >= 50:
                rj.description = text[:50000]
                fetched += 1
                log_json(
                    "deep_enrich_url_done",
                    url=rj.url[:500],
                    chars=len(text),
                    elapsed_ms=elapsed_ms,
                    detail_timeout_sec=timeout_sec,
                )
        except Exception as e:
            log_json("deep_enrich_url_error", url=rj.url[:500], error=str(e)[:500])

    return jobs, {
        "deep_enrich_skipped": False,
        "deep_enrich_fetched": fetched,
        "deep_enrich_max_jobs": max_n,
        "deep_enrich_detail_timeout_sec": timeout_sec,
    }
