from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime
from backend.app.db.base import Base


class CompanyBriefing(Base):
    __tablename__ = "company_briefings"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False, index=True)
    role_title = Column(String, nullable=False, index=True)
    
    # Stores the full structured briefing (Overview, Rounds, Culture, Topics)
    briefing_data = Column(JSON, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
