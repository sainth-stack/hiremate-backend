"""
Persisted ingestion run records for analytics and debugging (optional table).
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from backend.app.db.base import Base

_json = JSON().with_variant(JSONB(), "postgresql")


class ScraperRun(Base):
    """One row per ingest API invocation (career-pages or public-urls)."""

    __tablename__ = "scraper_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=False)
    source = Column(String(32), nullable=False, index=True)
    success = Column(Boolean, nullable=False, default=True)
    dry_run = Column(Boolean, nullable=False, default=False)
    error_summary = Column(Text, nullable=True)

    inserted = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    skipped = Column(Integer, nullable=False, default=0)
    filtered_out = Column(Integer, nullable=False, default=0)
    errors = Column(Integer, nullable=False, default=0)
    total_jobs_seen = Column(Integer, nullable=False, default=0)
    total_inserted = Column(Integer, nullable=False, default=0)
    total_filtered = Column(Integer, nullable=False, default=0)

    detail_json = Column(_json, nullable=True)
