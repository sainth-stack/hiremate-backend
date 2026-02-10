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


class UserResponse(BaseModel):
    """Schema for user response"""
    id: Optional[int] = None
    first_name: str
    last_name: str
    email: str
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    message: Optional[str] = None  # e.g. "User registered successfully" or "Login successful"
