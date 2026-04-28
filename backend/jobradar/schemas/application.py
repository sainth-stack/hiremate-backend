"""
Pydantic schemas for Application responses.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class HRContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime


class InterviewEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    event_type: str
    title: str
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    format: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None
    calendar_event_id: Optional[str] = None
    created_at: datetime
    
    @classmethod
    def model_validate(cls, obj, **kwargs):
        # Convert enum to string for serialization
        if hasattr(obj, 'event_type') and hasattr(obj.event_type, 'value'):
            obj.event_type = obj.event_type.value
        if hasattr(obj, 'format') and obj.format and hasattr(obj.format, 'value'):
            obj.format = obj.format.value
        return super().model_validate(obj, **kwargs)


class CompanyProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    domain: str
    name: Optional[str] = None
    industry: Optional[str] = None
    size_range: Optional[str] = None
    hq_location: Optional[str] = None
    description: Optional[str] = None
    linkedin_url: Optional[str] = None
    glassdoor_rating: Optional[float] = None
    founded_year: Optional[int] = None
    tech_stack: Optional[List[str]] = None
    last_enriched_at: Optional[datetime] = None


class StatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: str
    changed_at: datetime
    raw_email_id: Optional[str] = None
    summary: Optional[str] = None


class ApplicationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    company: str
    role: str
    platform: Optional[str] = None
    current_status: str
    applied_date: Optional[datetime] = None
    last_activity: datetime
    next_action: Optional[str] = None
    job_url: Optional[str] = None
    confidence: Optional[float] = None
    low_confidence: bool
    email_thread_id: Optional[str] = None
    interview_process: Optional[str] = None
    company_profile_id: Optional[int] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    salary_estimated_min: Optional[int] = None
    salary_estimated_max: Optional[int] = None
    created_at: datetime
    
    # Nested relationships
    hr_contacts: List[HRContactResponse] = []
    interview_events: List[InterviewEventResponse] = []
    company_profile: Optional[CompanyProfileResponse] = None
    status_history: List[StatusHistoryResponse] = []


class ApplicationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    company: str
    role: str
    platform: Optional[str] = None
    current_status: str
    applied_date: Optional[datetime] = None
    last_activity: datetime
    next_action: Optional[str] = None
    job_url: Optional[str] = None
    confidence: Optional[float] = None
    low_confidence: bool
    created_at: datetime
    
    # Summary fields only for list view
    interview_events_count: int = 0
    next_interview_at: Optional[datetime] = None


class HRContactCreate(BaseModel):
    name: str
    email: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
