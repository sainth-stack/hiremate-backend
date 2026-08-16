"""Admin-created Cartesia voice clones for interview TTS."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from backend.app.db.base import Base


class CustomVoiceClone(Base):
    __tablename__ = "custom_voice_clones"

    id = Column(Integer, primary_key=True, index=True)
    cartesia_voice_id = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    cartesia_language = Column(String(8), nullable=False, default="en")
    tts_language_code = Column(String(16), nullable=False, default="en-IN")
    source_filename = Column(String(255), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
