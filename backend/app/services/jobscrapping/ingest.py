"""
Upsert jobs by content_hash; return counters for API aggregates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.job import Job
from backend.app.services.jobscrapping.normalize import JobCreate


@dataclass
class IngestBatchResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
        }


def _row_equal(existing: Job, jc: JobCreate) -> bool:
    return (
        existing.title == jc.title
        and existing.company == jc.company
        and existing.location == jc.location
        and existing.url == jc.url
        and (existing.description or "") == (jc.description or "")
        and existing.remote == jc.remote
        and existing.salary_min == jc.salary_min
        and existing.salary_max == jc.salary_max
        and existing.posted_at == jc.posted_at
        and existing.source == jc.source
        and (existing.source_detail or {}) == (jc.source_detail or {})
    )


def upsert_jobs(
    db: Session,
    jobs: list[JobCreate],
    *,
    dry_run: bool = False,
    commit: bool = True,
) -> IngestBatchResult:
    """
    Insert or update by content_hash. If a row exists with identical fields, count as skipped.
    Per-row savepoints so one bad row does not abort the batch.
    Set ``commit=False`` when the caller commits with other rows (e.g. ``scraper_runs``).
    """
    out = IngestBatchResult()
    for jc in jobs:
        try:
            with db.begin_nested():
                existing = (
                    db.query(Job).filter(Job.content_hash == jc.content_hash).one_or_none()
                )
                if existing is None:
                    if dry_run:
                        out.inserted += 1
                    else:
                        row = Job(
                            title=jc.title,
                            company=jc.company,
                            location=jc.location,
                            url=jc.url,
                            description=jc.description,
                            remote=jc.remote,
                            salary_min=jc.salary_min,
                            salary_max=jc.salary_max,
                            posted_at=jc.posted_at,
                            source=jc.source,
                            source_detail=jc.source_detail,
                            content_hash=jc.content_hash,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                        db.add(row)
                        db.flush()
                        out.inserted += 1
                    continue
                if _row_equal(existing, jc):
                    out.skipped += 1
                    continue
                if dry_run:
                    out.updated += 1
                    continue
                existing.title = jc.title
                existing.company = jc.company
                existing.location = jc.location
                existing.url = jc.url
                existing.description = jc.description
                existing.remote = jc.remote
                existing.salary_min = jc.salary_min
                existing.salary_max = jc.salary_max
                existing.posted_at = jc.posted_at
                existing.source = jc.source
                existing.source_detail = jc.source_detail
                existing.updated_at = datetime.utcnow()
                out.updated += 1
        except Exception:
            out.errors += 1
    if not dry_run and commit:
        db.commit()
    return out


@dataclass
class PipelineMetrics:
    """Counters for ingestion API (plan.md)."""

    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    filtered_out: int = 0
    errors: int = 0
    total_jobs_seen: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    dry_run: bool = False
    detail: dict[str, Any] = field(default_factory=dict)

    def as_response(self) -> dict[str, Any]:
        # total_inserted aligns with inserted; total_filtered aligns with filtered_out
        return {
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "filtered_out": self.filtered_out,
            "errors": self.errors,
            "total_jobs_seen": self.total_jobs_seen,
            "total_inserted": self.inserted,
            "total_filtered": self.filtered_out,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "dry_run": self.dry_run,
            **self.detail,
        }
