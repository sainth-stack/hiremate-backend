"""
UserResume - stores multiple resumes per user for keyword analysis selection
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from backend.app.db.base import Base


class UserResume(Base):
    __tablename__ = "user_resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    resume_url = Column(String(512), nullable=False)
    resume_name = Column(String(255), nullable=False)  # e.g. "Sainathreddy_Guraka_resume (default)"
    resume_text = Column(Text, nullable=True)  # Extracted text for keyword matching
    is_default = Column(Integer, default=0)  # 1 = default resume for this user

    created_at = Column(DateTime, default=datetime.utcnow)
