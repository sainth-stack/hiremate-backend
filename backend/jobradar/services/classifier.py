"""
Email thread classifier.
The actual LLM call is delegated to whichever provider is configured via
AI_PROVIDER in .env (gemini | gpt | claude | mistral).
"""
from typing import Optional, List
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


class JDClassificationOutput(BaseModel):
    company: str
    role: str
    confidence: float = 0.0


class InterviewQuestionData(BaseModel):
    category: str
    question_text: str
    overview: Optional[str] = None
    intent: Optional[str] = None
    expectations: list[str] = []
    sample_answer: Optional[str] = None
    star_breakdown: dict[str, bool] = {"s": True, "t": True, "a": True, "r": True}
    complexity: str = "Medium"
    duration: str = "2-3 min"


class CultureSignal(BaseModel):
    signal: str
    detail: str
    icon_type: str = "FlashOnRoundedIcon"
    color: str = "#2563eb"


class InterviewRound(BaseModel):
    round: int
    name: str
    duration: str = "60 min"
    focus: str
    status: str = "upcoming"


class PrepTopic(BaseModel):
    topic: str
    priority: str = "medium"
    readiness: int = 50


class BriefingData(BaseModel):
    company: str
    role: str
    logo: str = "💳"
    industry: str
    size: str = "1,000+ employees"
    summary: str  # General summary of the company and role
    culture_signals: list[CultureSignal]
    interview_rounds: list[InterviewRound]
    topics_to_prep: list[PrepTopic]


def classify_thread(messages: list[dict]) -> Optional[ClassifierOutput]:
    """
    Classify email thread using the configured LLM provider.
    Returns None if the thread is not job-related.
    """
    from backend.jobradar.services.llm_factory import LLMFactory
    provider = LLMFactory.get_provider()
    return provider.classify_thread(messages)


def classify_jd(jd_text: str) -> Optional[JDClassificationOutput]:
    """
    Classify a job description using the configured LLM provider.
    Returns JDClassificationOutput with extracted company and role.
    """
    from backend.jobradar.services.llm_factory import LLMFactory
    provider = LLMFactory.get_provider()
    return provider.classify_jd(jd_text)


class InterviewEvaluationOutput(BaseModel):
    star_score: int  # 0-100
    star_breakdown: dict[str, bool]  # {s: bool, t: bool, a: bool, r: bool}
    feedback: str  # Expert feedback
    ai_coaching_tip: str  # One actionable improvement
