"""
TokenUsage - tracks AI token consumption for analytics and billing.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Float

from backend.app.db.base import Base


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    # Optional: null if background/system task OR if user not identified
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    
    # Model used: e.g. gpt-4o-mini, gemini-2.0-flash
    model = Column(String(100), nullable=False, index=True)
    # Provider: openai, google, anthropic, mistral
    provider = Column(String(50), nullable=False)
    
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Estimated cost in USD based on pricing at time of call
    cost = Column(Float, default=0.0)
    
    # Feature name: e.g. "resume_extraction", "sentinel_gmail", "cold_message"
    feature = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
