"""
Profile database model - stores resume/profile data in schema format
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from backend.app.db.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    resume_url = Column(String(512), nullable=True)
    resume_last_updated = Column(String(64), nullable=True)  # ISO date string

    first_name = Column(String(100), default="")
    last_name = Column(String(100), default="")
    email = Column(String(255), default="")
    phone = Column(String(50), default="")
    city = Column(String(100), default="")
    country = Column(String(100), default="")
    willing_to_work_in = Column(JSON, default=list)  # ["United States", ...]

    professional_headline = Column(String(120), default="")
    professional_summary = Column(Text, default="")

    experiences = Column(JSON, default=list)
    educations = Column(JSON, default=list)
    tech_skills = Column(JSON, default=list)
    soft_skills = Column(JSON, default=list)
    projects = Column(JSON, default=list)
    preferences = Column(JSON, default=dict)
    links = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="profile")
