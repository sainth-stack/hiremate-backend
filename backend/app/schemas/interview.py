"""Pydantic schemas for admin Interview endpoints."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from backend.app.services.voice.constants import VALID_LANGUAGE_CODES, VALID_SPEAKER_IDS

VALID_DIFFICULTIES = {"easy", "medium", "hard"}


def _validate_tts_speaker(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip().lower()
    if not v:
        return None
    if v not in VALID_SPEAKER_IDS:
        raise ValueError("tts_speaker must be one of the supported Sarvam voices")
    return v


def _validate_tts_language(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    if v not in VALID_LANGUAGE_CODES:
        raise ValueError("tts_language_code must be a supported BCP-47 language code")
    return v


class InterviewCreateRequest(BaseModel):
    title: str
    difficulty: str
    description: str
    question_count: int = 15

    @field_validator("question_count")
    @classmethod
    def question_count_valid(cls, v: int) -> int:
        count = int(v)
        if count < 3 or count > 30:
            raise ValueError("question_count must be between 3 and 30")
        return count

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title is required")
        return v[:255]

    @field_validator("difficulty")
    @classmethod
    def difficulty_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description is required")
        return v


class InterviewUpdateRequest(InterviewCreateRequest):
    """Same fields as create; used for PUT updates."""
    pass


class InterviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    difficulty: str
    description: str
    summary: str | None = None
    question_count: int = 15
    tts_speaker: str | None = None
    tts_language_code: str | None = None
    created_at: datetime


class InterviewQuestionCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order: int
    template: str
    view_card: dict
    time_card: dict
    category: str
    question_text: str
    overview: str | None = None
    intent: str | None = None
    expectations: list[str] = []
    sample_answer: str | None = None
    star_breakdown: dict | None = None
    complexity: str
    duration: str


class InterviewQuestionTextUpdate(BaseModel):
    id: int
    question_text: str

    @field_validator("question_text")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question_text is required")
        return v


class InterviewRegenerateQuestionsRequest(BaseModel):
    question_count: int | None = None

    @field_validator("question_count")
    @classmethod
    def question_count_valid(cls, v: int | None) -> int | None:
        if v is None:
            return None
        count = int(v)
        if count < 3 or count > 30:
            raise ValueError("question_count must be between 3 and 30")
        return count


class InterviewQuestionsUpdateRequest(BaseModel):
    questions: list[InterviewQuestionTextUpdate]

    @field_validator("questions")
    @classmethod
    def questions_not_empty(
        cls, v: list[InterviewQuestionTextUpdate]
    ) -> list[InterviewQuestionTextUpdate]:
        if not v:
            raise ValueError("questions must contain at least one item")
        return v


class InterviewDetailResponse(InterviewResponse):
    questions: list[InterviewQuestionCardResponse] = []


class InterviewListResponse(BaseModel):
    interviews: list[InterviewResponse]


class LaunchInterviewUserInput(BaseModel):
    id: int
    email: str

    @field_validator("email")
    @classmethod
    def email_not_empty(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("email is required")
        return v


class LaunchInterviewRequest(BaseModel):
    interview_id: int
    launch_name: str = ""
    title: str
    difficulty: str
    description: str
    created_at: datetime
    voice_provider: str = "cartesia"
    voice_id: str | None = None
    voice_label: str | None = None
    tts_language_code: str | None = "en-IN"
    users: list[LaunchInterviewUserInput]
    user_ids: list[int] = []
    user_emails: list[str] = []

    @field_validator("voice_provider")
    @classmethod
    def voice_provider_valid(cls, v: str) -> str:
        provider = (v or "").strip().lower()
        if provider not in {"cartesia"}:
            raise ValueError("voice_provider must be cartesia (Sarvam is used for STT only)")
        return provider

    @model_validator(mode="after")
    def apply_default_voice(self):
        from backend.app.services.voice.cartesia_service import get_default_cartesia_voice

        default = get_default_cartesia_voice()
        if not self.voice_id:
            self.voice_id = default["id"]
            if not self.voice_label:
                self.voice_label = str(default["label"])
        self.voice_provider = "cartesia"
        return self

    @field_validator("tts_language_code")
    @classmethod
    def launch_language_valid(cls, v: str | None) -> str | None:
        return _validate_tts_language(v) if v else "en-IN"

    @field_validator("launch_name")
    @classmethod
    def launch_name_valid(cls, v: str) -> str:
        return v.strip()[:255]

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title is required")
        return v[:255]

    @field_validator("difficulty")
    @classmethod
    def difficulty_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description is required")
        return v

    @field_validator("users")
    @classmethod
    def users_not_empty(cls, v: list[LaunchInterviewUserInput]) -> list[LaunchInterviewUserInput]:
        if not v:
            raise ValueError("users must contain at least one user")
        return v

    @field_validator("user_emails")
    @classmethod
    def normalize_emails(cls, v: list[str]) -> list[str]:
        return [email.strip().lower() for email in v if email and email.strip()]

    @model_validator(mode="after")
    def sync_user_lists(self) -> "LaunchInterviewRequest":
        from_users_ids = [user.id for user in self.users]
        from_users_emails = [user.email for user in self.users]

        if self.user_ids and self.user_ids != from_users_ids:
            raise ValueError("user_ids must match users[].id")
        if self.user_emails and self.user_emails != from_users_emails:
            raise ValueError("user_emails must match users[].email")

        self.user_ids = from_users_ids
        self.user_emails = from_users_emails
        return self


class LaunchInterviewUserResponse(BaseModel):
    id: int
    email: str
    interview_link: str


class LaunchAssignmentResponse(BaseModel):
    user_id: int
    interview_id: int
    url: str


class LaunchInterviewResponse(BaseModel):
    launched_count: int
    interview: InterviewDetailResponse
    assignments: list[LaunchAssignmentResponse]


class LaunchInterviewDetailResponse(BaseModel):
    """Extended launch payload kept for admin tooling."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    title: str
    difficulty: str
    description: str
    created_at: datetime
    launched_at: datetime
    user_ids: list[int]
    user_emails: list[str]
    users: list[LaunchInterviewUserResponse]
    launched_count: int
    assignments: list[LaunchAssignmentResponse]


class InterviewSummaryResponse(BaseModel):
    id: int
    title: str
    difficulty: str
    description: str
    summary: str | None = None
    created_at: datetime


class InterviewQuestionReviewResponse(BaseModel):
    """Full per-question review — loaded on demand when user expands a question."""
    order: int
    question: str
    user_answer: str
    what_you_said: str
    how_to_answer: str
    feedback: str | None = None
    score: int | None = None
    audio_key: str | None = None
    has_audio: bool = False


class InterviewQuestionSummaryResponse(BaseModel):
    """Lightweight question row for the results list (no answers until expanded)."""
    order: int
    question: str
    score: int | None = None


class InterviewReportResponse(BaseModel):
    score: int
    summary: str
    evaluation_summary: str = ""
    strengths: list[str] = []
    improvements: list[str] = []
    overall_score: int | None = None
    final_score: int | None = None
    feedback: str | None = None
    evaluation: str | None = None
    areas_for_improvement: list[str] | None = None
    weaknesses: list[str] | None = None
    average_question_score: int | None = None
    question_summaries: list[InterviewQuestionSummaryResponse] = []


class LiveInterviewQuestionResponse(BaseModel):
    id: int
    order: int
    question_text: str
    category: str | None = None
    complexity: str | None = None
    duration: str | None = None
    overview: str | None = None


class InterviewIntroResponse(InterviewSummaryResponse):
    questions: list[InterviewQuestionCardResponse] = []


class UserLaunchedInterviewResponse(BaseModel):
    status: str
    user_email: str
    interview: InterviewIntroResponse
    report: InterviewReportResponse | None = None


class LiveInterviewQuestionsResponse(BaseModel):
    questions: list[InterviewQuestionCardResponse]
    question_count: int | None = None
    voice_provider: str | None = None
    voice_id: str | None = None
    voice_label: str | None = None
    tts_speaker: str | None = None
    tts_language_code: str | None = None


class InterviewAnswerItem(BaseModel):
    question: str
    answer: str
    audio_key: str | None = None
    audio_url: str | None = None

    @field_validator("question", "answer")
    @classmethod
    def strip_value(cls, v: str) -> str:
        return v.strip()


class InterviewSubmitRequest(BaseModel):
    user_id: int
    interview_id: int
    jd: str
    answers: list[InterviewAnswerItem]

    @field_validator("jd")
    @classmethod
    def jd_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("jd is required")
        return v

    @field_validator("answers")
    @classmethod
    def answers_not_empty(cls, v: list[InterviewAnswerItem]) -> list[InterviewAnswerItem]:
        if not v:
            raise ValueError("answers must contain at least one item")
        return v


class InterviewSubmitResponse(InterviewReportResponse):
    user_id: int
    interview_id: int
    status: str = "completed"


class InterviewRetestRequest(BaseModel):
    user_id: int
    interview_id: int


class InterviewRetestResponse(BaseModel):
    user_id: int
    interview_id: int
    status: str = "pending"


class InterviewPerformanceResponse(InterviewReportResponse):
    user_id: int
    interview_id: int
    status: str
    submitted_at: datetime | None = None


class InterviewQuestionAnalysisResponse(InterviewQuestionReviewResponse):
    user_id: int
    interview_id: int


class SubmitLaunchedInterviewRequest(BaseModel):
    interview_id: int
    answers: dict | None = None
    notes: str | None = None


class SubmitLaunchedInterviewResponse(BaseModel):
    interview_id: int
    user_id: int
    status: str
    submitted_at: datetime
    message: str = "Interview submitted successfully"


class LaunchCampaignAssigneeSummary(BaseModel):
    id: int
    user_id: int
    user_email: str
    user_name: str | None = None
    status: str
    submitted_at: datetime | None = None
    score: int | None = None
    interview_url: str


class LaunchCampaignSummary(BaseModel):
    id: int
    launch_name: str
    interview_id: int
    interview_title: str
    difficulty: str
    launched_at: datetime
    launched_by_name: str | None = None
    launched_by_email: str | None = None
    total_assignees: int
    completed_count: int
    in_progress_count: int
    pending_count: int


class LaunchCampaignListResponse(BaseModel):
    launches: list[LaunchCampaignSummary]
    total: int


class LaunchCampaignAnswerItem(BaseModel):
    question: str
    answer: str
    order: int | None = None
    audio_key: str | None = None
    audio_url: str | None = None
    has_audio: bool = False


class LaunchCampaignAssigneeDetail(LaunchCampaignAssigneeSummary):
    answers: list[LaunchCampaignAnswerItem] = []
    report: InterviewReportResponse | None = None
    question_reviews: list[InterviewQuestionReviewResponse] = []


class LaunchCampaignDetailResponse(LaunchCampaignSummary):
    description: str
    summary: str | None = None
    interview_created_at: datetime | None = None
    assignees: list[LaunchCampaignAssigneeDetail] = []
