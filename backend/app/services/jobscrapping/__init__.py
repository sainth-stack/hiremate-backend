"""
Job ingestion pipeline: config → normalize → title filter → dedupe (content_hash) → upsert.

Exports runners for career pages (Playwright) and public URL feeds.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.services.jobscrapping.config import load_merged_config
from backend.app.services.jobscrapping.deep_enrich import enrich_raw_job_descriptions
from backend.app.services.jobscrapping.ingest import PipelineMetrics, upsert_jobs
from backend.app.services.jobscrapping.normalize import JobCreate, RawJob, job_result_to_raw_job, raw_to_job_create
from backend.app.services.jobscrapping.scrapping_algorithms import (
    fetch_all_public_feeds,
    scrape_enabled_companies,
)
from backend.app.services.jobscrapping.unified_ingest import run_unified_companies_ingestion
from backend.app.services.jobscrapping.scraper_runs import persist_scraper_run
from backend.app.services.jobscrapping.title_filter import parse_title_filter, title_passes_filter


def _apply_filter_and_upsert(
    db: Session,
    cfg: dict,
    raw_jobs: list[RawJob],
    *,
    source: str,
    dry_run: bool,
    scrape_failures: list[dict],
    commit: bool = True,
) -> PipelineMetrics:
    tf = parse_title_filter(cfg)
    total_seen = len(raw_jobs)
    filtered_out = 0
    passed: list[RawJob] = []
    for rj in raw_jobs:
        if not title_passes_filter(rj.title, tf):
            filtered_out += 1
        else:
            passed.append(rj)

    passed, enrich_meta = enrich_raw_job_descriptions(cfg, passed, dry_run=dry_run)

    to_persist: list[JobCreate] = []
    for rj in passed:
        if source == "career_page":
            sd: dict | None = {"scan_method": "playwright", "company": rj.company}
        else:
            ex = rj.extra or {}
            sd = {"feed": ex.get("feed"), "adapter": ex.get("adapter")}
            sd = {k: v for k, v in sd.items() if v is not None} or None
        to_persist.append(raw_to_job_create(rj, source=source, source_detail=sd))

    batch = upsert_jobs(db, to_persist, dry_run=dry_run, commit=commit)
    err_n = len(scrape_failures) + batch.errors
    detail: dict = {
        "source": source,
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
        total_jobs_seen=total_seen,
        dry_run=dry_run,
        detail=detail,
    )


def _run_ingest_with_run_record(
    db: Session,
    *,
    source_key: str,
    dry_run: bool,
    ingest_fn,
) -> PipelineMetrics:
    """Execute ingest, persist ``scraper_runs`` aligned with counters, single commit."""
    started_at = datetime.utcnow()
    try:
        m: PipelineMetrics = ingest_fn()
        rid = persist_scraper_run(
            db,
            started_at=started_at,
            source=source_key,
            dry_run=dry_run,
            metrics=m,
            success=True,
            error_summary=None,
        )
        detail = dict(m.detail)
        detail["scraper_run_id"] = rid
        m = PipelineMetrics(
            inserted=m.inserted,
            updated=m.updated,
            skipped=m.skipped,
            filtered_out=m.filtered_out,
            errors=m.errors,
            total_jobs_seen=m.total_jobs_seen,
            dry_run=m.dry_run,
            detail=detail,
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
                source=source_key,
                dry_run=dry_run,
                metrics=fail,
                success=False,
                error_summary=str(e)[:4000],
            )
            db.commit()
        except Exception:
            db.rollback()
        raise


def run_career_pages_ingestion(db: Session, *, dry_run: bool = False) -> PipelineMetrics:
    """
    Playwright listing pass per enabled `tracked_companies` with ``careers_url`` (see ``scrapping_algorithms.company_careers``).
    ``scan_method: websearch`` does not skip scraping; ``scan_query`` is unused here.
    Honors concurrency, retries, timeouts, circuit breaker from config.
    Optional deep enrich and ``scraper_runs`` persistence.
    """

    def _inner() -> PipelineMetrics:
        cfg = load_merged_config()
        job_results, failures, websearch_skipped, websearch_config_rows = scrape_enabled_companies(
            cfg
        )
        raw_jobs = [job_result_to_raw_job(jr) for jr in job_results]
        m = _apply_filter_and_upsert(
            db,
            cfg,
            raw_jobs,
            source="career_page",
            dry_run=dry_run,
            scrape_failures=failures,
            commit=False,
        )
        detail = dict(m.detail)
        detail["websearch_skipped"] = websearch_skipped
        detail["websearch_config_rows"] = websearch_config_rows
        return PipelineMetrics(
            inserted=m.inserted,
            updated=m.updated,
            skipped=m.skipped,
            filtered_out=m.filtered_out,
            errors=m.errors,
            total_jobs_seen=m.total_jobs_seen,
            dry_run=m.dry_run,
            detail=detail,
        )

    return _run_ingest_with_run_record(
        db, source_key="career_page", dry_run=dry_run, ingest_fn=_inner
    )


def run_public_urls_ingestion(db: Session, *, dry_run: bool = False) -> PipelineMetrics:
    """HTTP/JSON public feeds (``scrapping_algorithms.live_urls``)."""

    def _inner() -> PipelineMetrics:
        cfg = load_merged_config()
        raw_jobs, failures = fetch_all_public_feeds(cfg)
        return _apply_filter_and_upsert(
            db,
            cfg,
            raw_jobs,
            source="public_url",
            dry_run=dry_run,
            scrape_failures=failures,
            commit=False,
        )

    return _run_ingest_with_run_record(
        db, source_key="public_url", dry_run=dry_run, ingest_fn=_inner
    )


__all__ = [
    "run_career_pages_ingestion",
    "run_public_urls_ingestion",
    "run_unified_companies_ingestion",
    "PipelineMetrics",
]
