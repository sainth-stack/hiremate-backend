from sqlalchemy import Boolean, Column, Integer, String, DateTime, Float, Text, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.db.base import Base
import enum


class EventType(enum.Enum):
    interview = "interview"
    assessment = "assessment"
    technical_screen = "technical_screen"
    culture_fit = "culture_fit"
    offer_call = "offer_call"
    onboarding = "onboarding"


class MeetingFormat(enum.Enum):
    video = "video"
    phone = "phone"
    onsite = "onsite"
    async_format = "async"


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
    company_profile_id = Column(Integer, ForeignKey("company_profiles.id", ondelete="SET NULL"), nullable=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(3), nullable=True)
    salary_estimated_min = Column(Integer, nullable=True)
    salary_estimated_max = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships for eager loading
    hr_contacts = relationship("HRContact", back_populates="application", lazy="select")
    interview_events = relationship("InterviewEvent", back_populates="application", lazy="select")
    company_profile = relationship("CompanyProfile", foreign_keys=[company_profile_id], lazy="select")
    status_history = relationship("StatusHistory", back_populates="application", lazy="select")


class StatusHistory(Base):
    __tablename__ = "application_status_history"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_email_id = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    
    # Relationship
    application = relationship("Application", back_populates="status_history")


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


class HRContact(Base):
    __tablename__ = "hr_contacts"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    source_email_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    application = relationship("Application", back_populates="hr_contacts")


class InterviewEvent(Base):
    __tablename__ = "interview_events"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(Enum(EventType), nullable=False)
    title = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    format = Column(Enum(MeetingFormat), nullable=True)
    meeting_link = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    calendar_event_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    application = relationship("Application", back_populates="interview_events")


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    size_range = Column(String, nullable=True)
    hq_location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    linkedin_url = Column(String, nullable=True)
    glassdoor_rating = Column(Float, nullable=True)
    founded_year = Column(Integer, nullable=True)
    tech_stack = Column(JSON, nullable=True)
    last_enriched_at = Column(DateTime, nullable=True)
