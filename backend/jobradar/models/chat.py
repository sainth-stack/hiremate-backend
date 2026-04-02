from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from backend.app.db.base import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" or "model"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Pydantic Schemas ──────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

class ChatHistoryItem(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime
