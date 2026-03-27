"""
LegalPolicy — versioned storage for Privacy Policy / Terms of Service content.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String

from backend.app.db.base import Base


class LegalPolicy(Base):
    __tablename__ = "legal_policies"

    id = Column(Integer, primary_key=True, index=True)
    # "privacy_policy" | "terms_of_service"
    type = Column(String(50), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    # JSON: { effective_date, company_name, contact_email, sections: [{id, title, content}] }
    content = Column(JSON, nullable=False)
    is_current = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
