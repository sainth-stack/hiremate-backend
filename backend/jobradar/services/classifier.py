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


class InterviewEventData(BaseModel):
    event_type: str
    title: str
    scheduled_at: Optional[str] = None
    duration_minutes: Optional[int] = None
    format: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None


class HRContactData(BaseModel):
    name: str
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    title: Optional[str] = None


class CompanySignals(BaseModel):
    domain: Optional[str] = None
    industry: Optional[str] = None
    size_range: Optional[str] = None
    hq_location: Optional[str] = None
    tech_stack: list[str] = []


class SalaryRange(BaseModel):
    min: Optional[int] = None
    max: Optional[int] = None
    currency: Optional[str] = None


class ClassifierOutput(BaseModel):
    is_job_related: bool
    company: Optional[str] = None
    role: Optional[str] = None
    platform: Optional[str] = None
    status: Optional[str] = None
    stage_type: Optional[str] = None
    interview_date: Optional[str] = None
    next_action: Optional[str] = None
    confidence: float = 0.0
    summary: Optional[str] = None
    interview_process: Optional[str] = None
    interview_events: list[InterviewEventData] = []
    hr_contacts: list[HRContactData] = []
    company_signals: Optional[CompanySignals] = None
    salary_range: Optional[SalaryRange] = None


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


def classify_thread(messages: list[dict], user_id: int = None, email: str = None) -> Optional[ClassifierOutput]:
    """
    Classify email thread using the configured LLM provider.
    Returns None if the thread is not job-related.
    """
    from backend.jobradar.services.llm_factory import LLMFactory
    provider = LLMFactory.get_provider()
    return provider.classify_thread(messages, user_id=user_id, email=email)


def classify_jd(jd_text: str, user_id: int = None, email: str = None) -> Optional[JDClassificationOutput]:
    """
    Classify a job description using the configured LLM provider.
    Returns JDClassificationOutput with extracted company and role.
    """
    from backend.jobradar.services.llm_factory import LLMFactory
    provider = LLMFactory.get_provider()
    return provider.classify_jd(jd_text, user_id=user_id, email=email)


class InterviewEvaluationOutput(BaseModel):
    star_score: int  # 0-100
    star_breakdown: dict[str, bool]  # {s: bool, t: bool, a: bool, r: bool}
    feedback: str  # Expert feedback
    ai_coaching_tip: str  # One actionable improvement
