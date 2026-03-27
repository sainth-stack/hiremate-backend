"""
TailorContext - DB-backed storage for Tailor Resume context from extension.
Replaces the in-memory dict store with persistent records that survive server restarts.
Each record has a TTL (expires_at); stale records are cleaned up by the cleanup task.
"""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from backend.app.db.base import Base

_DEFAULT_TTL_HOURS = 4


class TailorContext(Base):
    __tablename__ = "tailor_contexts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        Integer,
        ForeignKey("user_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_description = Column(Text, nullable=False)
    job_title = Column(String(255), nullable=True)
    # source: extension | manual_paste | job_listing
    source = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow() + timedelta(hours=_DEFAULT_TTL_HOURS),
    )
