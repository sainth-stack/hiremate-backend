"""
Scheduled job ingestion from public APIs.
Runs every 2 hours to fetch latest jobs.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from backend.app.db.session import get_db_context
from backend.app.services.jobscrapping.public_apis import run_public_apis_ingestion_with_run_record

logger = get_logger("scheduler")

scheduler: AsyncIOScheduler | None = None


async def scheduled_job_ingestion():
    """
    Scheduled task to ingest jobs from public APIs.
    Runs every 2 hours.
    """
    logger.info("Starting scheduled job ingestion")
    start_time = datetime.now()
    
    try:
        with get_db_context() as db:
            metrics = await run_public_apis_ingestion_with_run_record(db, dry_run=False)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Scheduled job ingestion completed in {elapsed:.1f}s: "
                f"inserted={metrics.inserted}, updated={metrics.updated}, "
                f"skipped={metrics.skipped}, errors={metrics.errors}, "
                f"total={metrics.total_jobs_seen}"
            )
            
    except Exception as e:
        logger.error(f"Scheduled job ingestion failed: {e}", exc_info=True)


def start_scheduler():
    """
    Start the job ingestion scheduler.
    Runs every 2 hours, configurable via settings.
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler already running")
        return
    
    if not getattr(settings, "enable_job_scheduler", True):
        logger.info("Job scheduler disabled via settings")
        return
    
    schedule_interval_hours = getattr(settings, "job_ingestion_interval_hours", 2)
    
    scheduler = AsyncIOScheduler()
    
    scheduler.add_job(
        scheduled_job_ingestion,
        CronTrigger(hour=f"*/{schedule_interval_hours}"),
        id="job_ingestion",
        name="Public APIs Job Ingestion",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info(f"Job ingestion scheduler started (runs every {schedule_interval_hours} hours)")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global scheduler
    
    if scheduler is None:
        return
    
    scheduler.shutdown(wait=True)
    scheduler = None
    logger.info("Scheduler stopped")


def get_scheduler_status() -> dict:
    """Get current scheduler status and next run time."""
    if scheduler is None:
        return {"running": False, "next_run": None}
    
    jobs = scheduler.get_jobs()
    if not jobs:
        return {"running": True, "next_run": None, "jobs": []}
    
    job_info = []
    for job in jobs:
        job_info.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })
    
    return {
        "running": True,
        "jobs": job_info,
    }
