from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.db.base import Base


class MockInterviewQuestion(Base):
    __tablename__ = "mock_interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Context (Normalized for caching)
    company_name = Column(String, nullable=False, index=True) 
    role_title = Column(String, nullable=False, index=True)
    
    # Question Data
    category = Column(String, nullable=False)  # Behavioral, Technical, HR
    question_text = Column(Text, nullable=False)
    overview = Column(Text)
    intent = Column(Text)
    expectations = Column(JSON)  # List of strings
    sample_answer = Column(Text)
    star_breakdown = Column(JSON)  # Dict: {s: bool, t: bool, a: bool, r: bool}
    
    # Metadata
    complexity = Column(String, default="Medium")
    duration = Column(String, default="2-3 min")
    is_global = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MockInterviewSession(Base):
    __tablename__ = "mock_interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    
    total_score = Column(Integer, default=0) # Average STAR score
    duration_seconds = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    answers = relationship("MockInterviewAnswer", back_populates="session", cascade="all, delete-orphan")


class MockInterviewAnswer(Base):
    __tablename__ = "mock_interview_answers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("mock_interview_sessions.id"), nullable=False)
    
    question_text = Column(Text, nullable=False)
    category = Column(String)
    user_answer = Column(Text, nullable=False)
    
    # AI Evaluation results
    star_score = Column(Integer, default=0)
    star_breakdown = Column(JSON) # {s: bool, t: bool, a: bool, r: bool}
    ai_feedback = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("MockInterviewSession", back_populates="answers")
