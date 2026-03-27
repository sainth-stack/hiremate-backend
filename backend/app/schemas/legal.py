"""Pydantic schemas for Legal Policy endpoints."""
from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel


class PolicySection(BaseModel):
    id: str
    title: str
    content: str


class LegalPolicyResponse(BaseModel):
    id: int
    type: str
    version: str
    title: str
    content: Dict[str, Any]
    is_current: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LegalPolicyHistoryItem(BaseModel):
    id: int
    type: str
    version: str
    title: str
    is_current: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class LegalPolicyUpsertRequest(BaseModel):
    version: str
    title: str
    content: Dict[str, Any]
