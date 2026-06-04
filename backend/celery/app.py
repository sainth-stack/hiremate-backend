"""
Celery application — job ingestion only.

Run from hiremate-backend/ with PYTHONPATH=.:
  celery -A backend.celery.app worker -Q ingest -c 2 -l info
  celery -A backend.celery.app beat -l info
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from backend.app.core.config import settings
from backend.app.core.logging_config import setup_logging

setup_logging()

broker_url = settings.celery_broker_url or settings.redis_url
result_backend = settings.celery_result_backend or settings.redis_url

if not broker_url:
    broker_url = "memory://"
    result_backend = "cache+memory://"

celery_app = Celery(
    "hiremate",
    broker=broker_url,
    backend=result_backend,
    include=[
        "backend.celery.workers.ingestion",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

_interval = max(1, min(settings.job_ingestion_interval_hours, 24))

celery_app.conf.beat_schedule = {
    "job-ingestion": {
        "task": "backend.celery.workers.ingestion.run_public_apis_ingestion",
        "schedule": crontab(minute=0, hour=f"*/{_interval}"),
        "options": {"queue": "ingest"},
    },
}

if not settings.enable_job_scheduler:
    celery_app.conf.beat_schedule.pop("job-ingestion", None)
