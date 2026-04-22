"""Persist ``ScraperRun`` rows aligned with API response counters."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.models.scraper_run import ScraperRun
from backend.app.services.jobscrapping.ingest import PipelineMetrics


def persist_scraper_run(
    db: Session,
    *,
    started_at: datetime,
    source: str,
    dry_run: bool,
    metrics: PipelineMetrics,
    success: bool,
    error_summary: str | None,
) -> int:
    """Insert one row and flush so ``id`` is available. Caller commits."""
    detail = dict(metrics.detail)
    row = ScraperRun(
        started_at=started_at,
        ended_at=datetime.utcnow(),
        source=source,
        success=success,
        dry_run=dry_run,
        error_summary=error_summary,
        inserted=metrics.inserted,
        updated=metrics.updated,
        skipped=metrics.skipped,
        filtered_out=metrics.filtered_out,
        errors=metrics.errors,
        total_jobs_seen=metrics.total_jobs_seen,
        total_inserted=metrics.inserted,
        total_filtered=metrics.filtered_out,
        total_tokens=metrics.total_tokens,
        total_cost=metrics.total_cost,
        detail_json=detail,
    )
    db.add(row)
    db.flush()
    return int(row.id)
