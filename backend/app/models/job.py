"""
Global job corpus (ingested listings) — not per-user user_jobs.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from backend.app.db.base import Base

# JSON on SQLite; JSONB on PostgreSQL
_source_detail_type = JSON().with_variant(JSONB(), "postgresql")


class Job(Base):
    """Ingested job posting row; deduplicated by content_hash."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False)
    company = Column(String(512), nullable=False)
    location = Column(String(512), nullable=True)
    url = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    remote = Column(Boolean, nullable=False, default=False)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    source = Column(String(64), nullable=False, index=True)
    source_detail = Column(_source_detail_type, nullable=True)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
