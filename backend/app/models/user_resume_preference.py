"""
UserResumePreference - per-user resume editor preferences.
Stored one row per user; created on first save, defaults returned when missing.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.base import Base


class UserResumePreference(Base):
    __tablename__ = "user_resume_preferences"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    default_template_id = Column(String(50), nullable=False, default="classic-pro")
    default_font_family = Column(String(100), nullable=False, default="Inter")
    default_color_scheme = Column(String(50), nullable=False, default="default")
    preferred_paper_size = Column(String(10), nullable=False, default="A4")
    default_tone = Column(String(20), nullable=False, default="professional")
    show_keyword_score = Column(Boolean, nullable=False, default=True)
    auto_save_ms = Column(SmallInteger, nullable=False, default=300)
    preferred_sections = Column(JSONB, nullable=True, default=list)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow)
