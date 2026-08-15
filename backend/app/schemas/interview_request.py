"""Pydantic schemas for interview request workflow."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class InterviewRequestCreateBody(BaseModel):
    domain: str
    description: str

    @field_validator("domain")
    @classmethod
    def domain_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("domain is required")
        return v[:255]

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description is required")
        return v


class InterviewRequestCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    description: str
    status: str
    created_at: datetime


class MyAdminInterviewItem(BaseModel):
    id: int
    request_id: int | None = None
    interview_id: int | None = None
    domain: str
    description: str
    status: str
    created_at: datetime
    launched_at: datetime | None = None
    completed_at: datetime | None = None
    score: int | None = None
    interview_url: str | None = None
    user_id: int


class MyAdminInterviewsResponse(BaseModel):
    interviews: list[MyAdminInterviewItem]


class AdminInterviewRequestItem(BaseModel):
    id: int
    user_id: int
    user_email: str
    user_name: str
    domain: str
    description: str
    status: str
    created_at: datetime
    launched_at: datetime | None = None
    interview_id: int | None = None
    interview_url: str | None = None
    score: int | None = None


class AdminInterviewRequestListResponse(BaseModel):
    requests: list[AdminInterviewRequestItem]


class LaunchInterviewRequestBody(BaseModel):
    interview_id: int
    title: str
    difficulty: str
    description: str
    user_id: int
    user_email: str

    @field_validator("title", "description")
    @classmethod
    def strip_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field is required")
        return v

    @field_validator("difficulty")
    @classmethod
    def difficulty_valid(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("user_email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        return v.strip().lower()


class LaunchInterviewRequestResponse(BaseModel):
    launched_count: int = 1
    interview_url: str
    status: str = "pending"
    request_id: int
    interview_id: int
    user_id: int
