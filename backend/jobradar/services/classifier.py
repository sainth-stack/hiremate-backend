"""
Email thread classifier.
The actual LLM call is delegated to whichever provider is configured via
AI_PROVIDER in .env (gemini | gpt | claude | mistral).
"""
from typing import Optional
from pydantic import BaseModel

VALID_STATUSES = {
    "applied", "acknowledged", "in_review",
    "interview_scheduled", "interview_completed",
    "offer_received", "rejected", "ghosted",
}


class ScoreResponse(BaseModel):
    score: float          # 0–100
    verdict: str          # "Strong Match", "Moderate Match", "Weak Match"
    matched_skills: list[str]
    missing_skills: list[str]
    summary: str
    suggestions: list[str]  # Actionable advice for optimization


class ClassifierOutput(BaseModel):
    is_job_related: bool
    company: Optional[str] = None
    role: Optional[str] = None
    platform: Optional[str] = None
    status: Optional[str] = None
    interview_date: Optional[str] = None
    next_action: Optional[str] = None
    confidence: float = 0.0
    summary: Optional[str] = None
    interview_process: Optional[str] = None


def classify_thread(messages: list[dict]) -> Optional[ClassifierOutput]:
    """
    Classify email thread using the configured LLM provider.
    Returns None if the thread is not job-related.
    """
    from backend.jobradar.services.llm_factory import LLMFactory
    provider = LLMFactory.get_provider()
    return provider.classify_thread(messages)
