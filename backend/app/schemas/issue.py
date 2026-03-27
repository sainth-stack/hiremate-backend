"""Pydantic schemas for Issue Report endpoints."""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


VALID_CATEGORIES = {"bug", "feature_request", "ui_issue", "performance", "other"}
VALID_STATUSES = {"open", "in_progress", "resolved"}
VALID_SOURCES = {"web", "extension"}


class IssueCreateRequest(BaseModel):
    title: str
    description: str
    category: str
    source: str = "web"
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title is required")
        return v[:255]

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description is required")
        return v

    @field_validator("category")
    @classmethod
    def category_valid(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {VALID_CATEGORIES}")
        return v

    @field_validator("source")
    @classmethod
    def source_valid(cls, v: str) -> str:
        if v not in VALID_SOURCES:
            raise ValueError(f"source must be one of {VALID_SOURCES}")
        return v


class IssueStatusUpdateRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    title: str
    description: str
    category: str
    status: str
    source: str
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    # ORM attr is issue_metadata (to avoid SQLAlchemy reserved name); serialize as "metadata"
    metadata: Optional[Dict[str, Any]] = Field(None, validation_alias="issue_metadata")
    screenshot_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class IssueListResponse(BaseModel):
    items: list[IssueResponse]
    total: int
    page: int
    page_size: int
