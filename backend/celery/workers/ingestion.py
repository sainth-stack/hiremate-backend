"""Ingest queue — job corpus from public APIs."""
from __future__ import annotations

import asyncio
from datetime import datetime

from backend.celery.app import celery_app
from backend.app.core.logging_config import get_logger
from backend.app.db.session import get_db_context
from backend.app.services.jobscrapping.public_apis import run_public_apis_ingestion_with_run_record

logger = get_logger("celery.workers.ingestion")


@celery_app.task(name="backend.celery.workers.ingestion.run_public_apis_ingestion", bind=True)
def run_public_apis_ingestion(self):
    """Ingest jobs from configured public APIs."""
    logger.info("Celery: starting public APIs job ingestion")
    start_time = datetime.now()

    async def _run():
        with get_db_context() as db:
            return await run_public_apis_ingestion_with_run_record(db, dry_run=False)

    try:
        metrics = asyncio.run(_run())
        elapsed = (datetime.now() - start_time).total_seconds()
        result = {
            "inserted": metrics.inserted,
            "updated": metrics.updated,
            "skipped": metrics.skipped,
            "errors": metrics.errors,
            "total_jobs_seen": metrics.total_jobs_seen,
            "elapsed_sec": round(elapsed, 1),
        }
        logger.info("Celery: job ingestion completed: %s", result)
        return result
    except Exception as exc:
        logger.error("Celery: job ingestion failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=300, max_retries=2) from exc
