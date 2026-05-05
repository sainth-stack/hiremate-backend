from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text
from datetime import datetime
from backend.app.db.base import Base

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    amount = Column(Integer, default=0)  # In Paise
    
    # Quotas
    resume_slots = Column(Integer, default=0)
    ai_tailor_credits = Column(Integer, default=0)
    ats_match_checks = Column(Integer, default=0)
    job_tracking = Column(Integer, default=0)
    
    # Extra features as a list of strings/objects
    features = Column(JSON, default=list)
    
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)  # Drives "Most Popular" badge on pricing page
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
