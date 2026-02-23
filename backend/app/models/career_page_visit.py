"""
CareerPageVisit - tracks user activity on career/job pages (autofill used, save job, etc.)
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from backend.app.db.base import Base


class CareerPageVisit(Base):
    __tablename__ = "career_page_visits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # page_url = career page or job page URL
    page_url = Column(String(2048), nullable=False)
    # company_name extracted from page or user input
    company_name = Column(String(255), nullable=True)
    # job_url = specific job posting URL (when on job detail page or saved job)
    job_url = Column(String(2048), nullable=True)
    # action_type: autofill_used, save_job, page_view
    action_type = Column(String(50), nullable=False)
    # job_title when available (e.g. from save job form)
    job_title = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
