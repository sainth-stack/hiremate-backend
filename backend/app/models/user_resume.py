"""
UserResume - stores multiple resumes per user for keyword analysis selection.
Each resume can carry its own profile snapshot (for per-JD customization)
and the job context it was generated for.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, SmallInteger, String, Text

from backend.app.db.base import Base


class UserResume(Base):
    __tablename__ = "user_resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    resume_url = Column(String(512), nullable=False)
    resume_name = Column(String(255), nullable=False)  # e.g. "Sainathreddy_Guraka_resume (default)"
    resume_text = Column(Text, nullable=True)  # Extracted text for keyword matching
    is_default = Column(Integer, default=0)  # 1 = default resume for this user

    # Per-JD profile snapshot: stores the exact profile data used/edited for this resume.
    # Allows each generated resume to carry its own profile customization independent of
    # the global Profile table. Schema matches ProfilePayload (camelCase JSON).
    resume_profile_snapshot = Column(JSON, nullable=True)

    # Job context for which this resume was generated
    job_title = Column(String(255), nullable=True)
    job_description_snippet = Column(Text, nullable=True)  # First 1000 chars of JD

    # Version tracking - FK to resume_versions.id (UUID string)
    current_version_id = Column(String(36), nullable=True)
    sections_order = Column(JSON, nullable=True)  # User's drag-reordered section list
    design_config = Column(JSON, nullable=True)   # Fonts, colors, margins per resume
    keyword_score = Column(SmallInteger, nullable=True)  # 0-100 match score vs JD
    keyword_details = Column(JSON, nullable=True)
    # status: generating | ready | error
    status = Column(String(20), nullable=False, default="ready")
    template_id = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
