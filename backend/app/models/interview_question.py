"""Generated questions for admin interview templates."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text

from backend.app.db.base import Base


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_index = Column(Integer, nullable=False, default=0)
    template = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)
    question_text = Column(Text, nullable=False)
    overview = Column(Text, nullable=True)
    intent = Column(Text, nullable=True)
    expectations = Column(JSON, nullable=True)
    sample_answer = Column(Text, nullable=True)
    star_breakdown = Column(JSON, nullable=True)
    complexity = Column(String(20), nullable=False)
    duration = Column(String(20), nullable=False, default="2-3 min")
    view_card = Column(JSON, nullable=False)
    time_card = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
