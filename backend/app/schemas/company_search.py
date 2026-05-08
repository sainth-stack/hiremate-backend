"""
Schemas for Company Job Search feature.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class JobCorpusItem(BaseModel):
    """Row from global ingested ``jobs`` table."""

    id: int
    title: str
    company: str
    location: Optional[str] = None
    url: str
    description: Optional[str] = None
    remote: bool
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    posted_at: Optional[datetime] = None
    source: str
    created_at: datetime
    match_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class JobCorpusPage(BaseModel):
    items: List[JobCorpusItem | Dict[str, Any]]
    total: int
    page: int
    page_size: int


class CompanyItem(BaseModel):
    name: str
    section: Optional[str] = None


class ParseResponse(BaseModel):
    companies: List[CompanyItem]


class LinksRequest(BaseModel):
    companies: List[CompanyItem]
    role: Optional[str] = None
    location: Optional[str] = None


class CompanyLinks(BaseModel):
    name: str
    career_url: Optional[str] = None
    linkedin_search_url: Optional[str] = None


class LinksResponse(BaseModel):
    results: List[CompanyLinks]


class JobResult(BaseModel):
    title: str
    url: Optional[str] = None
    location: Optional[str] = None
    snippet: Optional[str] = None


class JobEvent(BaseModel):
    company: str
    jobs: List[JobResult]
    status: Literal["pending", "done", "error"]
    message: Optional[str] = None
