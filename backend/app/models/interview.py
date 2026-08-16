"""Admin-managed interview templates."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.app.db.base import Base


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    difficulty = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    tts_speaker = Column(String(64), nullable=True)
    tts_language_code = Column(String(16), nullable=True)
    question_count = Column(Integer, nullable=False, default=15)
    created_at = Column(DateTime, default=datetime.utcnow)
