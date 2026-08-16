"""Admin-launched interview assignments to users."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class LaunchedInterview(Base):
    __tablename__ = "launched_interviews"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    difficulty = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    interview_created_at = Column(DateTime, nullable=True)
    launched_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    launch_name = Column(String(255), nullable=True)
    launched_at = Column(DateTime, default=datetime.utcnow)
    voice_provider = Column(String(32), nullable=True)
    voice_id = Column(String(128), nullable=True)
    voice_label = Column(String(255), nullable=True)
    tts_language_code = Column(String(16), nullable=True)
    question_count = Column(Integer, nullable=True)
    silence_submit_seconds = Column(Integer, nullable=False, default=10)
    pause_duration_seconds = Column(Integer, nullable=False, default=10)
    max_pauses_per_interview = Column(Integer, nullable=False, default=3)

    assignments = relationship(
        "LaunchedInterviewUser",
        back_populates="launch",
        cascade="all, delete-orphan",
    )


class LaunchedInterviewUser(Base):
    __tablename__ = "launched_interview_users"

    id = Column(Integer, primary_key=True, index=True)
    launched_interview_id = Column(
        Integer,
        ForeignKey("launched_interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_email = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    submitted_at = Column(DateTime, nullable=True)
    submission_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    launch = relationship("LaunchedInterview", back_populates="assignments")
