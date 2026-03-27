"""
ResumeVersion - stores version history for each UserResume.
Each generated or tailored resume creates a new version record.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.base import Base


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resume_id = Column(
        Integer,
        ForeignKey("user_resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(SmallInteger, nullable=False)

    # Full profile snapshot used for this version
    profile_snapshot = Column(JSONB, nullable=True)
    # Design settings (fonts, colors, margins, template)
    design_config = Column(JSONB, nullable=True)

    # What triggered this version: initial_generate | tailor_more | manual_edit | upload | section_edit
    trigger = Column(String(30), nullable=True)

    keyword_score = Column(SmallInteger, nullable=True)
    keyword_details = Column(JSONB, nullable=True)
    jd_snapshot = Column(Text, nullable=True)  # Full JD used for this version

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("resume_id", "version_number", name="uq_resume_version"),
    )
