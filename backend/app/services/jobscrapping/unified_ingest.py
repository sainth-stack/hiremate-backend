"""
Per tracked company: parallel portal passes — career Playwright (listing caps), company-search
pipeline (HTTP + ATS adapters on the same URL), optional corporate site, public-feed slice,
Indeed RSS, LinkedIn / Naukri (best-effort HTML).
"""
from __future__ import annotations

import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from sqlalchemy.orm import Session

from backend.app.services.company_search.career import CareerPageScraper
from backend.app.services.jobscrapping.config import load_merged_config
from backend.app.services.jobscrapping.deep_enrich import enrich_raw_job_descriptions
from backend.app.services.jobscrapping.ingest import PipelineMetrics, upsert_jobs
from backend.app.services.jobscrapping.normalize import JobCreate, RawJob, job_result_to_raw_job, raw_to_job_create
from backend.app.services.jobscrapping.scraper_runs import persist_scraper_run
from backend.app.services.jobscrapping.scrapping_algorithms.company_careers import USER_AGENTS, scrape_single_company_careers
from backend.app.services.jobscrapping.scrapping_algorithms.live_urls import fetch_all_public_feeds
from backend.app.services.jobscrapping.scrapping_algorithms.third_party_job_feeds import (
    bucket_public_jobs_by_company,
    fetch_indeed_rss_raw_jobs,
    fetch_linkedin_guest_raw_jobs,
    fetch_naukri_search_raw_jobs,
)
from backend.app.services.jobscrapping.title_filter import parse_title_filter, title_passes_filter

logger = logging.getLogger(__name__)
_PREFIX = "[ingest:unified]"


DEFAULT_UNIFIED_SOURCES: dict[str, bool] = {
    "career_page": True,
    "company_search": True,
    "company_website": True,
    "public_feed_match": True,
    "indeed_rss": True,
    "linkedin": True,
    "naukri": True,
}


def _source_flags(settings: dict[str, Any]) -> dict[str, bool]:
    ui = settings.get("unified_ingest") if isinstance(settings.get("unified_ingest"), dict) else {}
    raw = ui.get("sources") if isinstance(ui.get("sources"), dict) else {}
    out = dict(DEFAULT_UNIFIED_SOURCES)
    for k, v in raw.items():
        if isinstance(k, str) and isinstance(v, bool):
            out[k] = v
    return out


def _portal_pause_sec(settings: dict[str, Any]) -> float:
    ui = settings.get("unified_ingest") if isinstance(settings.get("unified_ingest"), dict) else {}
    v = ui.get("portal_request_pause_sec")
    try:
        return max(0.0, min(5.0, float(v)))
    except (TypeError, ValueError):
        return 0.35


def _company_search_params(cfg: dict[str, Any]) -> tuple[str, list[str], str, bool]:
    """role, skills, location, use_playwright_on_search (second browser on same URL)."""
    ui = cfg.get("settings", {}).get("unified_ingest")
    if not isinstance(ui, dict):
        return "", [], "", False
    cs = ui.get("company_search")
    if not isinstance(cs, dict):
        return "", [], "", False
    role = (cs.get("role") or "").strip()
    skills_raw = cs.get("skills")
    skills: list[str] = []
    if isinstance(skills_raw, list):
        skills = [str(s).strip() for s in skills_raw if str(s).strip()]
    elif isinstance(skills_raw, str) and skills_raw.strip():
        skills = [skills_raw.strip()]
    location = (str(cs.get("location") or "")).strip()
    use_pw = bool(cs.get("use_playwright"))
    return role, skills, location, use_pw


def _scraper_timeout_sec(settings: dict[str, Any]) -> int:
    try:
        return int(max(15, min(120, float(settings.get("company_timeout_sec") or 90))))
    except (TypeError, ValueError):
        return 60


def _apply_filter_enrich_upsert(
    db: Session,
    cfg: dict[str, Any],
    labeled: list[tuple[RawJob, str, dict[str, Any] | None]],
    *,
    dry_run: bool,
    scrape_failures: list[dict[str, Any]],
    commit: bool,
) -> PipelineMetrics:
    tf = parse_title_filter(cfg)
    filtered_out = 0
    kept_rj: list[RawJob] = []
    meta: list[tuple[str, dict[str, Any] | None]] = []
    for rj, src, extra in labeled:
        if not title_passes_filter(rj.title, tf):
            filtered_out += 1
            continue
        kept_rj.append(rj)
        meta.append((src, extra))

    kept_rj, enrich_meta = enrich_raw_job_descriptions(cfg, kept_rj, dry_run=dry_run)

    to_persist: list[JobCreate] = []
    for rj, (src, extra) in zip(kept_rj, meta):
        detail: dict[str, Any] = dict(extra or {})
        if src in ("career_page", "company_website"):
            detail.setdefault("scan_method", "playwright")
            detail.setdefault("company", rj.company)
        if src == "company_search":
            detail.setdefault("scan_method", "company_search")
            detail.setdefault("company", rj.company)
        if rj.extra:
            detail = {**rj.extra, **detail}
        sd = {k: v for k, v in detail.items() if v is not None} or None
        to_persist.append(raw_to_job_create(rj, source=src, source_detail=sd))

    batch = upsert_jobs(db, to_persist, dry_run=dry_run, commit=commit)
    err_n = len(scrape_failures) + batch.errors
    
    # Capture AI usage from enrichment
    tokens = enrich_meta.get("total_tokens", 0)
    cost = enrich_meta.get("total_cost", 0.0)
    
    detail: dict[str, Any] = {
        "failures": scrape_failures,
        "ingest_batch_errors": batch.errors,
        "deep_enrich": enrich_meta,
    }
    return PipelineMetrics(
        inserted=batch.inserted,
        updated=batch.updated,
        skipped=batch.skipped,
        filtered_out=filtered_out,
        errors=err_n,
        total_jobs_seen=len(labeled),
        total_tokens=tokens,
        total_cost=cost,
        dry_run=dry_run,
        detail=detail,
    )


def _ingest_one_company(
    cfg: dict[str, Any],
    row: dict[str, Any],
    public_by_company: dict[str, list[RawJob]],
    *,
    ua: str,
) -> tuple[list[tuple[RawJob, str, dict[str, Any] | None]], list[dict[str, Any]]]:
    settings = cfg.get("settings") or {}
    flags = _source_flags(settings)
    ui_cfg = settings.get("unified_ingest") if isinstance(settings.get("unified_ingest"), dict) else {}
    try:
        portal_parallelism = int(ui_cfg.get("portal_parallelism") or 8)
    except (TypeError, ValueError):
        portal_parallelism = 8
    portal_parallelism = max(2, min(16, portal_parallelism))

    pause = _portal_pause_sec(settings)
    name = (row.get("name") or "unknown").strip()
    failures: list[dict[str, Any]] = []
    labeled: list[tuple[RawJob, str, dict[str, Any] | None]] = []
    labeled_lock = threading.Lock()

    def _track_extra() -> dict[str, Any]:
        return {"tracked_company": name}

    role, skills, location, search_use_pw = _company_search_params(cfg)
    http_timeout = float(settings.get("http_timeout_sec") or 30)
    scraper_timeout = _scraper_timeout_sec(settings)

    careers_url = (row.get("careers_url") or "").strip()
    site_url = (row.get("website_jobs_url") or row.get("website_url") or "").strip()
    site_distinct = bool(site_url and site_url.rstrip("/") != careers_url.rstrip("/"))

    # Public feed rows (no HTTP here — already fetched globally)
    if flags.get("public_feed_match", True):
        for rj in public_by_company.get(name, []):
            labeled.append((rj, "public_url", {**_track_extra(), **(rj.extra or {})}))

    callables: list[tuple[str, Callable[[], tuple[list[tuple[RawJob, str, dict[str, Any] | None]], list[dict[str, Any]]]]]] = []

    def _wrap_career_pw(url: str, source: str) -> Callable[
        [],
        tuple[list[tuple[RawJob, str, dict[str, Any] | None]], list[dict[str, Any]]],
    ]:
        def _run() -> tuple[list[tuple[RawJob, str, dict[str, Any] | None]], list[dict[str, Any]]]:
            jobs, fails = scrape_single_company_careers(cfg, name, url, user_agent=ua)
            rows = [(job_result_to_raw_job(j), source, _track_extra()) for j in jobs]
            return rows, fails

        return _run

    def _wrap_company_search(url: str, tag: str, use_playwright: bool) -> Callable[
        [],
        tuple[list[tuple[RawJob, str, dict[str, Any] | None]], list[dict[str, Any]]],
    ]:
        def _run() -> tuple[list[tuple[RawJob, str, dict[str, Any] | None]], list[dict[str, Any]]]:
            try:
                scraper = CareerPageScraper(timeout_seconds=scraper_timeout)
                jobs, meta = scraper.extract_jobs_from_careers_url(
                    url, name, role=role, skills=skills, use_playwright=use_playwright
                )
                loc_f = (location or "").strip()
                if loc_f:
                    jobs = [j for j in jobs if scraper.location_matches(j.location, loc_f)]
                extra_base = _track_extra()
                extra_detail = {
                    **extra_base,
                    "pipeline": meta.get("status"),
                    "ats_provider": meta.get("ats_provider"),
                    "canonical_url": meta.get("url"),
                }
                rows = [(job_result_to_raw_job(j), tag, extra_detail) for j in jobs]
                return rows, []
            except Exception as e:
                logger.warning("%s company_search failed | company=%s url=%s | %s", _PREFIX, name, url, e)
                return [], [{"kind": "company_search", "target": name, "url": url, "message": str(e)}]

        return _run

    def _wrap_indeed() -> tuple[list[tuple[RawJob, str, dict[str, Any] | None]], list[dict[str, Any]]]:
        time.sleep(pause + random.uniform(0, 0.15))
        raws, fails = fetch_indeed_rss_raw_jobs(name, timeout_sec=http_timeout)
        return [(rj, "indeed", _track_extra()) for rj in raws], fails

    def _wrap_linkedin() -> tuple[list[tuple[RawJob, str, dict[str, Any] | None]], list[dict[str, Any]]]:
        time.sleep(pause + random.uniform(0, 0.15))
        raws, fails = fetch_linkedin_guest_raw_jobs(name, timeout_sec=http_timeout)
        return [(rj, "linkedin", _track_extra()) for rj in raws], fails

    def _wrap_naukri() -> tuple[list[tuple[RawJob, str, dict[str, Any] | None]], list[dict[str, Any]]]:
        time.sleep(pause + random.uniform(0, 0.15))
        raws, fails = fetch_naukri_search_raw_jobs(name, timeout_sec=http_timeout)
        return [(rj, "naukri", _track_extra()) for rj in raws], fails

    if careers_url and flags.get("career_page", True):
        callables.append(("career_playwright", _wrap_career_pw(careers_url, "career_page")))
    if careers_url and flags.get("company_search", True):
        # HTTP + ATS first (no extra Playwright vs listing pass unless configured)
        callables.append(("company_search_ats_careers", _wrap_company_search(careers_url, "company_search", False)))
        if search_use_pw:
            callables.append(
                ("company_search_pw_careers", _wrap_company_search(careers_url, "company_search", True))
            )
    if site_url and flags.get("company_website", True) and site_distinct:
        callables.append(("website_playwright", _wrap_career_pw(site_url, "company_website")))
        if flags.get("company_search", True):
            callables.append(("company_search_ats_website", _wrap_company_search(site_url, "company_search", False)))
            if search_use_pw:
                callables.append(
                    ("company_search_pw_website", _wrap_company_search(site_url, "company_search", True))
                )

    if flags.get("indeed_rss", True):
        callables.append(("indeed_rss", _wrap_indeed))
    if flags.get("linkedin", True):
        callables.append(("linkedin", _wrap_linkedin))
    if flags.get("naukri", True):
        callables.append(("naukri", _wrap_naukri))

    if callables:
        max_workers = min(portal_parallelism, len(callables))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {pool.submit(fn): label for label, fn in callables}
            for fut in as_completed(future_map):
                label = future_map[fut]
                try:
                    rows, fails = fut.result()
                    with labeled_lock:
                        labeled.extend(rows)
                        failures.extend(fails)
                except Exception as e:
                    logger.exception("%s portal task %s crashed | company=%s", _PREFIX, label, name)
                    failures.append({"kind": "unified_portal", "target": name, "portal": label, "message": str(e)})

    logger.info("%s company=%s | raw_labeled_rows=%d | failures=%d", _PREFIX, name, len(labeled), len(failures))
    return labeled, failures


def run_unified_companies_ingestion(db: Session, *, dry_run: bool = False) -> PipelineMetrics:
    """
    For each enabled ``tracked_companies`` row, run portal tasks in parallel (career Playwright,
    company-search ATS pipeline on careers + optional website URL, Indeed / LinkedIn / Naukri).
    """
    from datetime import datetime

    started_at = datetime.utcnow()
    try:
        cfg = load_merged_config()
        settings = cfg.get("settings") or {}
        ui_cfg = settings.get("unified_ingest") if isinstance(settings.get("unified_ingest"), dict) else {}
        concurrency = max(1, int(ui_cfg.get("concurrency") or settings.get("concurrency") or 4))

        tracked = [r for r in (cfg.get("tracked_companies") or []) if isinstance(r, dict) and r.get("enabled", True) is not False]

        public_raw: list[RawJob] = []
        pub_failures: list[dict[str, Any]] = []
        if _source_flags(settings).get("public_feed_match", True):
            public_raw, pub_failures = fetch_all_public_feeds(cfg)

        public_by_company = bucket_public_jobs_by_company(public_raw, tracked)

        all_labeled: list[tuple[RawJob, str, dict[str, Any] | None]] = []
        all_failures: list[dict[str, Any]] = list(pub_failures)
        lock = threading.Lock()
        ua_rot = 0

        logger.info(
            "%s === run | companies=%d | concurrency=%d | public_feed_jobs=%d ===",
            _PREFIX,
            len(tracked),
            concurrency,
            len(public_raw),
        )

        def _work(r: dict[str, Any]) -> None:
            nonlocal ua_rot
            with lock:
                ua = USER_AGENTS[ua_rot % len(USER_AGENTS)]
                ua_rot += 1
            time.sleep(random.uniform(0.05, 0.35))
            labeled, fails = _ingest_one_company(cfg, r, public_by_company, ua=ua)
            with lock:
                all_labeled.extend(labeled)
                all_failures.extend(fails)

        with ThreadPoolExecutor(max_workers=min(concurrency, max(1, len(tracked)))) as ex:
            futs = [ex.submit(_work, row) for row in tracked]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    logger.exception("%s worker failed: %s", _PREFIX, e)
                    with lock:
                        all_failures.append({"kind": "unified_company", "message": str(e)})

        m = _apply_filter_enrich_upsert(
            db,
            cfg,
            all_labeled,
            dry_run=dry_run,
            scrape_failures=all_failures,
            commit=False,
        )
        by_source: dict[str, int] = {}
        for _, src, _ in all_labeled:
            by_source[src] = by_source.get(src, 0) + 1
        detail = dict(m.detail)
        detail["unified_sources_seen"] = by_source
        detail["public_feed_fetch_failures"] = len(pub_failures)
        m = PipelineMetrics(
            inserted=m.inserted,
            updated=m.updated,
            skipped=m.skipped,
            filtered_out=m.filtered_out,
            errors=m.errors,
            total_jobs_seen=m.total_jobs_seen,
            total_tokens=m.total_tokens,
            total_cost=m.total_cost,
            dry_run=m.dry_run,
            detail=detail,
        )
        rid = persist_scraper_run(
            db,
            started_at=started_at,
            source="unified_company",
            dry_run=dry_run,
            metrics=m,
            success=True,
            error_summary=None,
        )
        detail2 = dict(m.detail)
        detail2["scraper_run_id"] = rid
        detail2["unified_ingest_explanation"] = {
            "filtered_out": (
                "Rows removed only by ``title_filter`` after scraping (``match_all`` uses negatives; else positive keywords). "
                "Region/department hub links are filtered out earlier during listing / embedded-JSON extraction."
            ),
            "unified_sources_seen": (
                "Per-source counts of raw rows **before** title filter. "
                "``company_search`` only appears when the HTTP+ATS path returns jobs without Playwright "
                "(e.g. Greenhouse/Lever API on first fetch); custom JS sites often show 0 here while "
                "``career_page`` has Playwright results."
            ),
            "indeed_rss": (
                "Unofficial RSS; Indeed often returns 403/404 for automated clients. Those cases are skipped "
                "without ingest errors. Use Indeed Publisher / partner APIs for reliable coverage."
            ),
            "public_url": (
                "Non-zero only when a ``public_urls`` feed job's employer string matches a tracked company "
                "(see ``company_name_aliases`` on the company row)."
            ),
        }
        m = PipelineMetrics(
            inserted=m.inserted,
            updated=m.updated,
            skipped=m.skipped,
            filtered_out=m.filtered_out,
            errors=m.errors,
            total_jobs_seen=m.total_jobs_seen,
            total_tokens=m.total_tokens,
            total_cost=m.total_cost,
            dry_run=m.dry_run,
            detail=detail2,
        )
        db.commit()
        return m
    except Exception as e:
        db.rollback()
        fail = PipelineMetrics(
            inserted=0,
            updated=0,
            skipped=0,
            filtered_out=0,
            errors=1,
            total_jobs_seen=0,
            dry_run=dry_run,
            detail={"failures": [{"kind": "ingest", "message": str(e)[:2000]}]},
        )
        try:
            persist_scraper_run(
                db,
                started_at=started_at,
                source="unified_company",
                dry_run=dry_run,
                metrics=fail,
                success=False,
                error_summary=str(e)[:4000],
            )
            db.commit()
        except Exception:
            db.rollback()
        raise
