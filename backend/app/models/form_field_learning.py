"""Models for form field mapping learning engine - per-user and shared knowledge."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class SharedFormStructure(Base):
    """Shared form structure cache - domain/URL pattern, field fingerprints, confidence."""
    __tablename__ = "shared_form_structures"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), nullable=False, index=True)
    url_pattern = Column(String(500), nullable=True)
    ats_platform = Column(String(50), nullable=True)
    field_count = Column(Integer, nullable=True)
    field_fps = Column(JSON, nullable=True)  # list of field fingerprints
    has_resume_upload = Column(Boolean, default=False)
    has_cover_letter = Column(Boolean, default=False)
    is_multi_step = Column(Boolean, default=False)
    step_count = Column(Integer, default=1)
    confidence = Column(Float, default=0.5)
    sample_count = Column(Integer, default=1)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class SharedSelectorPerformance(Base):
    """Shared selector performance - best selectors per field fingerprint + ATS."""
    __tablename__ = "shared_selector_performance"

    id = Column(Integer, primary_key=True, index=True)
    field_fp = Column(String(64), nullable=False, index=True)
    ats_platform = Column(String(50), nullable=False)
    selector_type = Column(String(20), nullable=False)
    selector = Column(Text, nullable=False)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    last_success = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, default=datetime.utcnow)


class SharedFieldProfileKey(Base):
    """Shared field fingerprint -> profile key mapping. No user values stored."""
    __tablename__ = "shared_field_profile_keys"

    field_fp = Column(String(64), primary_key=True)
    ats_platform = Column(String(50), nullable=True)
    label_norm = Column(String(255), nullable=True)
    profile_key = Column(String(100), nullable=False)
    confidence = Column(Float, default=0.8)
    vote_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserFieldAnswer(Base):
    """Per-user learned answer values - field fingerprint -> value."""
    __tablename__ = "user_field_answers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    field_fp = Column(String(64), nullable=False, index=True)
    label_norm = Column(String(255), nullable=True)
    value = Column(Text, nullable=True)
    source = Column(String(20), default="llm")  # llm | user_edit | form_submit
    confidence = Column(Float, default=0.8)
    used_count = Column(Integer, default=1)
    last_used = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "field_fp", name="uq_user_fp"),)


class UserSubmissionHistory(Base):
    """Per-user submission history for learning from form submits."""
    __tablename__ = "user_submission_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(String(255), nullable=True)
    url = Column(String(500), nullable=True)
    ats_platform = Column(String(50), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    field_count = Column(Integer, nullable=True)
    filled_count = Column(Integer, nullable=True)
    unfilled_profile_keys = Column(JSON, nullable=True)
    submitted_fields = Column(JSON, nullable=True)
