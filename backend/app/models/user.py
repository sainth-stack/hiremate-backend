"""
User database model
"""
from sqlalchemy import Boolean, Column, Integer, String, DateTime, JSON
from datetime import datetime
from backend.app.db.base import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Nullable for OAuth-only users
    
    # Google OAuth fields
    google_id = Column(String, unique=True, index=True, nullable=True)
    avatar_url = Column(String, nullable=True)
    google_access_token = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    last_history_id = Column(String, nullable=True)  # Gmail incremental sync
    # Present in DB (NOT NULL); must be set on insert — password/OAuth registration both omit Gmail until linked
    gmail_sync_enabled = Column(Boolean, default=False, nullable=False)
    is_active = Column(Integer, default=1)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    # User profile fields for salary estimation
    years_of_experience = Column(Integer, nullable=True)
    skills = Column(JSON, nullable=True)  # Array of skill strings
    current_location = Column(String, nullable=True)
    current_salary = Column(Integer, nullable=True)
    target_salary_min = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
