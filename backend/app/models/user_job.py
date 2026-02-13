"""
UserJob - stores saved jobs per user (Edit Job Description form)
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from backend.app.db.base import Base


class UserJob(Base):
    __tablename__ = "user_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    company = Column(String(255), default="")
    position_title = Column(String(255), default="")
    location = Column(String(255), default="")
    min_salary = Column(String(50), nullable=True)
    max_salary = Column(String(50), nullable=True)
    currency = Column(String(20), default="USD")
    period = Column(String(50), default="Yearly")  # Yearly, Monthly, Hourly
    job_type = Column(String(50), default="Full-Time")  # Full-Time, Part-Time, Contract, etc.
    job_description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    application_status = Column(String(100), default="I have not yet applied")
    job_posting_url = Column(String(1024), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
