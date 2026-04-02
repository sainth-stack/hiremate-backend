from sqlalchemy import Boolean, Column, Integer, String, DateTime, Float, Text, ForeignKey
from datetime import datetime
from backend.app.db.base import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    platform = Column(String, nullable=True)
    current_status = Column(String, default="applied", nullable=False)
    applied_date = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    next_action = Column(String, nullable=True)
    job_url = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    low_confidence = Column(Boolean, default=False)
    email_thread_id = Column(String, unique=True, nullable=True, index=True)
    interview_process = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StatusHistory(Base):
    __tablename__ = "application_status_history"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_email_id = Column(String, nullable=True)
    summary = Column(Text, nullable=True)


class SyncStatus(Base):
    __tablename__ = "sync_status"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    status = Column(String, default="idle", nullable=False)  # idle, running, stopped, completed, error
    total_threads = Column(Integer, default=0)
    parsed_count = Column(Integer, default=0)
    ai_count = Column(Integer, default=0)
    ai_success_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
