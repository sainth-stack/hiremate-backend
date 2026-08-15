"""Pydantic schemas for admin Interview endpoints."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

VALID_DIFFICULTIES = {"easy", "medium", "hard"}


class InterviewCreateRequest(BaseModel):
    title: str
    difficulty: str
    description: str

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
    title: str
    difficulty: str
    description: str
    created_at: datetime
    users: list[LaunchInterviewUserInput]
    user_ids: list[int] = []
    user_emails: list[str] = []

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


class InterviewAnswerItem(BaseModel):
    question: str
    answer: str

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
