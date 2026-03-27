"""
IssueReport — user-submitted bug reports / feature requests from web or extension.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text

from backend.app.db.base import Base


class IssueReport(Base):
    __tablename__ = "issue_reports"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    # bug | feature_request | ui_issue | performance | other
    category = Column(String(50), nullable=False)
    # open | in_progress | resolved
    status = Column(String(20), nullable=False, default="open")
    # web | extension
    source = Column(String(20), nullable=False, default="web")

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Denormalized for quick display without joining users table
    user_email = Column(String(255), nullable=True)

    # Captured browser metadata: { browser, url, os, user_agent, version }
    # "metadata" is reserved by SQLAlchemy Declarative — use issue_metadata as the Python attr
    issue_metadata = Column("metadata", JSON, nullable=True)
    screenshot_url = Column(String(512), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
