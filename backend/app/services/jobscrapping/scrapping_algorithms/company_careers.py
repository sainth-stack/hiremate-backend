"""
Company career-site scraping (Playwright): YAML-driven concurrency, retries, timeouts,
circuit breaker, structured JSON logs. Skips disabled companies only.

Every enabled company with ``careers_url`` is scraped with Playwright. ``scan_method: websearch``
and ``scan_query`` are hints for a future search-based ingest only; they do not skip Playwright here.

Reuses `CareerPageScraper.scrape_careers_listing_for_ingestion` (rich listings, scroll,
load more, pagination) with caps from `settings`.

Live in :mod:`backend.app.services.jobscrapping.scrapping_algorithms` alongside :mod:`live_urls`.
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any

from backend.app.services.company_search.base import JobResult
from backend.app.services.company_search.career import CareerPageScraper

logger = logging.getLogger(__name__)

# Human-readable console lines (uvicorn stdout). JSON lines remain for log aggregators.
_PREFIX = "[ingest:career-pages]"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def log_json(event: str, **fields: Any) -> None:
    """Single-line JSON for log aggregators."""
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, default=str))


class _CircuitBreaker:
    def __init__(self, max_consecutive: int) -> None:
        self._max = max(1, int(max_consecutive))
        self._consecutive = 0
        self._tripped = False
        self._lock = threading.Lock()

    def record_success(self) -> None:
        with self._lock:
            self._consecutive = 0

    def record_failure(self) -> bool:
        """Return True if breaker tripped on this failure."""
        with self._lock:
            self._consecutive += 1
            if self._consecutive >= self._max:
                self._tripped = True
                return True
            return False

    def is_open(self) -> bool:
        with self._lock:
            return self._tripped


def _chunked(items: list[Any], size: int) -> list[list[Any]]:
    out: list[list[Any]] = []
    for i in range(0, len(items), size):
        out.append(items[i : i + size])
    return out


def _run_playwright_with_timeout(
    scraper: CareerPageScraper,
    careers_url: str,
    company_name: str,
    *,
    pw_kwargs: dict[str, Any],
    timeout_sec: float,
) -> list[JobResult]:
    """Isolate Playwright in a one-off worker thread with hard timeout."""

    def _call() -> list[JobResult]:
        return scraper.scrape_careers_listing_for_ingestion(careers_url, company_name, **pw_kwargs)

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_call)
        return list(fut.result(timeout=timeout_sec))


def _playwright_kwargs_for_company(merged_config: dict[str, Any], timeout_sec: float, user_agent: str) -> dict[str, Any]:
    settings = merged_config.get("settings") or {}
    listing_max_scroll = int(settings.get("listing_max_scroll_rounds") or 15)
    listing_max_load_more = int(settings.get("listing_max_load_more_rounds") or 15)
    listing_max_pages = int(settings.get("listing_max_pages") or 20)
    return {
        "max_scroll_rounds": listing_max_scroll,
        "max_load_more_rounds": listing_max_load_more,
        "max_next_page_rounds": listing_max_pages,
        "listing_max_pages": listing_max_pages,
        "user_agent": user_agent,
        "default_timeout_ms": int(min(timeout_sec * 1000, 180_000)),
    }


def scrape_single_company_careers(
    merged_config: dict[str, Any],
    company_name: str,
    careers_url: str,
    *,
    user_agent: str | None = None,
) -> tuple[list[JobResult], list[dict[str, Any]]]:
    """
    Run one Playwright career listing (same caps/timeouts as batch ingest).
    Used by unified per-company ingest and by :func:`scrape_enabled_companies`.
    """
    settings = merged_config.get("settings") or {}
    retries = max(0, int(settings.get("retries") or 3))
    company_timeout_sec = float(settings.get("company_timeout_sec") or 90)
    timeout_sec = max(15.0, min(company_timeout_sec, 180.0))
    ua = user_agent or USER_AGENTS[0]
    scraper = CareerPageScraper(timeout_seconds=int(min(max(timeout_sec, 20.0), 120.0)))
    pw_kwargs = _playwright_kwargs_for_company(merged_config, timeout_sec, ua)
    last_err: str | None = None
    for attempt in range(retries + 1):
        if attempt > 0:
            logger.warning(
                "%s retry | company=%s | attempt %d/%d",
                _PREFIX,
                company_name,
                attempt + 1,
                retries + 1,
            )
        t0 = time.monotonic()
        try:
            jobs = _run_playwright_with_timeout(
                scraper,
                careers_url,
                company_name,
                pw_kwargs=pw_kwargs,
                timeout_sec=timeout_sec,
            )
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "%s single | company=%s | jobs_found=%d | elapsed_ms=%d",
                _PREFIX,
                company_name,
                len(jobs),
                elapsed_ms,
            )
            log_json(
                "career_company_done",
                company=company_name,
                careers_url=careers_url,
                jobs_found=len(jobs),
                elapsed_ms=elapsed_ms,
                attempt=attempt,
            )
            return jobs, []
        except FutureTimeout:
            last_err = f"timeout_after_{int(timeout_sec)}s"
            logger.warning("%s error | company=%s | %s", _PREFIX, company_name, last_err)
            log_json(
                "career_company_error",
                company=company_name,
                careers_url=careers_url,
                error=last_err,
                attempt=attempt,
            )
        except Exception as e:
            last_err = str(e)
            logger.warning("%s error | company=%s | %s", _PREFIX, company_name, last_err)
            log_json(
                "career_company_error",
                company=company_name,
                careers_url=careers_url,
                error=last_err,
                attempt=attempt,
            )
        time.sleep(0.4 * (2**attempt))
    return [], [
        {
            "kind": "career_company",
            "target": company_name,
            "url": careers_url,
            "message": last_err or "failed_after_retries",
        }
    ]


def scrape_enabled_companies(
    merged_config: dict[str, Any],
) -> tuple[list[JobResult], list[dict[str, Any]], int, int]:
    """
    Run Playwright listing for every enabled company with ``careers_url``.

    Returns ``(job_results, failures, websearch_skipped_legacy, websearch_config_hint_count)``.
    ``websearch_skipped_legacy`` is always ``0`` (nothing skipped for websearch).
    ``websearch_config_hint_count`` is how many rows had ``scan_method: websearch`` in config
    (informational; they were still scraped via Playwright on ``careers_url``).
    """
    settings = merged_config.get("settings") or {}
    companies_cfg = merged_config.get("tracked_companies") or []

    concurrency = max(1, int(settings.get("concurrency") or 8))
    retries = max(0, int(settings.get("retries") or 3))
    company_timeout_sec = float(settings.get("company_timeout_sec") or 90)
    breaker_max = int(settings.get("circuit_breaker_max_consecutive_failures") or 10)

    # Wall-clock per company (Playwright + scroll/pagination). SPAs rarely finish under 45s.
    timeout_sec = max(15.0, min(company_timeout_sec, 180.0))

    work: list[dict[str, Any]] = []
    websearch_config_hint_count = 0
    for row in companies_cfg:
        if row.get("enabled", True) is False:
            continue
        method = (row.get("scan_method") or "playwright").strip().lower()
        if method == "websearch":
            websearch_config_hint_count += 1
        url = (row.get("careers_url") or "").strip()
        name = (row.get("name") or "unknown").strip()
        if not url:
            continue
        work.append({"name": name, "url": url, "row": row})

    total_work = len(work)
    logger.info(
        "%s === run | playwright_queue=%d company(s) | websearch_hint_in_config=%d "
        "(Playwright still uses careers_url; scan_query ignored) | "
        "concurrency=%d | company_timeout_sec=%.1f | retries=%d | circuit_breaker_after=%d failures ===",
        _PREFIX,
        total_work,
        websearch_config_hint_count,
        concurrency,
        timeout_sec,
        retries,
        breaker_max,
    )
    if total_work:
        logger.info("%s progress 0/%d (0%%) — queued", _PREFIX, total_work)

    failures: list[dict[str, Any]] = []
    all_results: list[JobResult] = []
    results_lock = threading.Lock()
    progress_lock = threading.Lock()
    completed_n = 0
    breaker = _CircuitBreaker(breaker_max)
    ua_rot = 0

    def _record_company_finished(company_name: str) -> None:
        nonlocal completed_n
        if not total_work:
            return
        with progress_lock:
            completed_n += 1
            cur = completed_n
        pct = min(100, (100 * cur) // total_work)
        logger.info("%s progress %d/%d (%d%%) | last_done=%s", _PREFIX, cur, total_work, pct, company_name)
        log_json("career_progress", done=cur, total=total_work, percent=pct, company=company_name)

    def one_company(entry: dict[str, Any]) -> None:
        nonlocal ua_rot
        name = entry["name"]
        url = entry["url"]
        try:
            if breaker.is_open():
                return
            logger.info(
                "%s processing | company=%s | url=%s | thread=%s",
                _PREFIX,
                name,
                url,
                threading.current_thread().name,
            )
            time.sleep(random.uniform(0.15, 0.85))
            ua = USER_AGENTS[ua_rot % len(USER_AGENTS)]
            ua_rot += 1
            jobs, scrape_fails = scrape_single_company_careers(
                merged_config, name, url, user_agent=ua
            )
            if not scrape_fails:
                with results_lock:
                    all_results.extend(jobs)
                breaker.record_success()
                return

            last_err = (scrape_fails[0].get("message") if scrape_fails else None) or "failed_after_retries"
            tripped = breaker.record_failure()
            logger.error(
                "%s FAILED | company=%s | last_error=%s",
                _PREFIX,
                name,
                last_err,
            )
            failures.append(
                {
                    "kind": "career_company",
                    "target": name,
                    "url": url,
                    "message": last_err,
                    "circuit_breaker_tripped": tripped,
                }
            )
            if tripped:
                logger.error(
                    "%s circuit breaker OPEN — remaining queued companies will be skipped (max %d consecutive failures)",
                    _PREFIX,
                    breaker_max,
                )
                log_json(
                    "career_circuit_breaker_tripped",
                    consecutive_failures=breaker_max,
                )
        finally:
            _record_company_finished(name)

    batches = _chunked(work, concurrency)
    n_batches = len(batches)
    for batch_idx, batch in enumerate(batches, start=1):
        if breaker.is_open():
            logger.warning(
                "%s stopping before batch %d/%d — circuit breaker is open",
                _PREFIX,
                batch_idx,
                n_batches,
            )
            break
        names_in_batch = ", ".join(str(e["name"]) for e in batch)
        logger.info(
            "%s batch %d/%d | parallel=%d | %s",
            _PREFIX,
            batch_idx,
            n_batches,
            len(batch),
            names_in_batch,
        )
        with ThreadPoolExecutor(max_workers=len(batch)) as ex:
            futs = [ex.submit(one_company, e) for e in batch]
            for fut in futs:
                try:
                    fut.result()
                except Exception as e:
                    logger.exception("%s worker thread failed: %s", _PREFIX, e)
                    log_json("career_company_worker_crash", error=str(e))

    logger.info(
        "%s === finished | total_job_rows=%d | failures=%d | websearch_config_hint=%d ===",
        _PREFIX,
        len(all_results),
        len(failures),
        websearch_config_hint_count,
    )
    return all_results, failures, 0, websearch_config_hint_count
