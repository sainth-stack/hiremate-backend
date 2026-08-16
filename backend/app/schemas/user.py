"""
User Pydantic schemas for request/response validation
"""
from pydantic import BaseModel
from typing import Optional


class UserRegister(BaseModel):
    """Schema for user registration"""
    first_name: str
    last_name: str
    email: str
    password: str


class UserLogin(BaseModel):
    """Schema for user login"""
    email: str
    password: str


class InterviewSessionRequest(BaseModel):
    """Exchange interview link token for a user session."""
    user_id: int
    interview_id: int
    token: str


class UserResponse(BaseModel):
    """Schema for user response"""
    id: Optional[int] = None
    first_name: str
    last_name: str
    email: str
    is_admin: Optional[bool] = False
    gmail_sync_enabled: Optional[bool] = False
    token_balance: Optional[int] = 0
    monthly_tokens: Optional[int] = 0
    subscription_plan: Optional[str] = "free"
    total_tokens_consumed: Optional[int] = 0
    last_token_reset: Optional[str] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    message: Optional[str] = None  # e.g. "User registered successfully" or "Login successful"


class AdminCreateUserRequest(BaseModel):
    """Admin-created user (no auto-login)."""
    first_name: str
    last_name: str
    email: str
    password: str
    is_admin: bool = False


class AdminUserSummary(BaseModel):
    """User row returned from admin list/create."""
    id: int
    email: str
    first_name: str
    last_name: str
    created_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    jobs_count: int = 0
    career_visits_count: int = 0
    is_admin: bool = False
