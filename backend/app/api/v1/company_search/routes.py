# Nginx production config for SSE endpoint:
# location /api/company-search/jobs/stream {
#     proxy_pass http://backend;
#     proxy_buffering off;
#     proxy_cache off;
#     proxy_set_header Connection '';
#     proxy_http_version 1.1;
#     chunked_transfer_encoding on;
# }

"""
Company Job Search API endpoints.
"""
import asyncio
import json
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.core.dependencies import get_current_user
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.schemas.company_search import CompanyLinks, LinksRequest, LinksResponse, ParseResponse
from backend.app.services.company_search_service import (
    MAX_COMPANIES_PER_REQUEST,
    parse_file,
    resolve_links,
    search_jobs_for_company,
)

router = APIRouter(tags=["company-search"])
logger = get_logger("api.company_search")


@router.post("/company-search/parse", response_model=ParseResponse)
async def parse_company_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Parse a PDF/DOCX file and extract company names via LLM."""
    filename = file.filename or ""
    if not (filename.lower().endswith(".pdf") or filename.lower().endswith(".docx")):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    contents = await file.read()
    try:
        companies = await parse_file(contents, filename, user_id=current_user.id)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("parse_company_file failed user_id=%s filename=%s", current_user.id, filename)
        raise HTTPException(status_code=500, detail="Failed to parse file")

    return ParseResponse(companies=companies)


@router.post("/company-search/links", response_model=LinksResponse)
async def get_company_links(
    body: LinksRequest,
    current_user: User = Depends(get_current_user),
):
    """Resolve official careers page and LinkedIn search URLs for a list of companies."""
    if len(body.companies) > MAX_COMPANIES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many companies. Max {MAX_COMPANIES_PER_REQUEST} per request.",
        )

    try:
        results = await resolve_links(
            companies=body.companies,
            role=body.role or "",
            location=body.location or "",
            user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to resolve links")

    return LinksResponse(results=results)


class JobsRequest(BaseModel):
    companies: List[CompanyLinks]
    role: Optional[str] = None
    skills: Optional[List[str]] = None
    location: Optional[str] = None


async def _job_event_generator(
    companies: List[CompanyLinks],
    role: str,
    skills: List[str],
    location: str,
    user_id: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    tasks = [
        search_jobs_for_company(company, role, skills, location, user_id=user_id)
        for company in companies
    ]
    try:
        for coro in asyncio.as_completed(tasks):
            event = await coro
            yield f"data: {event.model_dump_json()}\n\n"
        yield 'data: {"status":"complete"}\n\n'
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled by client disconnect user_id=%s", user_id)


@router.post("/company-search/jobs/stream")
async def stream_jobs(
    body: JobsRequest,
    current_user: User = Depends(get_current_user),
):
    """Stream job results per company via SSE."""
    if len(body.companies) > MAX_COMPANIES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many companies. Max {MAX_COMPANIES_PER_REQUEST} per request.",
        )
    return StreamingResponse(
        _job_event_generator(
            companies=body.companies,
            role=body.role or "",
            skills=body.skills or [],
            location=body.location or "",
            user_id=current_user.id,
        ),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.post("/company-search/jobs")
async def batch_jobs(
    body: JobsRequest,
    current_user: User = Depends(get_current_user),
):
    """Collect all job results and return as a flat JSON list."""
    if len(body.companies) > MAX_COMPANIES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many companies. Max {MAX_COMPANIES_PER_REQUEST} per request.",
        )
    tasks = [
        search_jobs_for_company(c, body.role or "", body.skills or [], body.location or "", user_id=current_user.id)
        for c in body.companies
    ]
    results = await asyncio.gather(*tasks)
    return [json.loads(event.model_dump_json()) for event in results]
