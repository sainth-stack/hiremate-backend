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
from datetime import date, datetime, time
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.core.logging_config import get_logger
from backend.app.models.job import Job
from backend.app.models.user import User
from backend.app.schemas.company_search import (
    CompanyLinks,
    JobCorpusItem,
    JobCorpusPage,
    LinksRequest,
    LinksResponse,
    ParseResponse,
)
from backend.app.services.company_search_service import (
    MAX_COMPANIES_PER_REQUEST,
    parse_file,
    resolve_links,
    search_jobs_for_company,
)
from backend.app.services.job_matching_service import calculate_job_match
from backend.app.models.profile import Profile

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
        companies = await parse_file(contents, filename, user_id=current_user.id, email=current_user.email)
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


@router.get(
    "/company-search/jobs/corpus",
    response_model=JobCorpusPage,
)
def list_jobs_corpus(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    q: Optional[str] = Query(
        None,
        description="Search across job title, company name, and description",
    ),
    company: Optional[str] = Query(None, description="Filter by company name (partial match)"),
    role: Optional[str] = Query(None, description="Filter by job title / role (partial match)"),
    location: Optional[str] = Query(None, description="Filter by location (partial match)"),
    skills: Optional[str] = Query(
        None,
        description="Comma-separated skills; each must appear in title or description",
    ),
    experience_levels: Optional[str] = Query(
        None,
        description="Comma-separated experience levels (entry, mid, senior, lead, staff)",
    ),
    job_types: Optional[str] = Query(
        None,
        description="Comma-separated job types (full-time, part-time, contract, internship)",
    ),
    work_modes: Optional[str] = Query(
        None,
        description="Comma-separated work modes (remote, onsite, hybrid)",
    ),
    posted_from: Optional[date] = Query(None, description="Include jobs posted on or after this date (UTC)"),
    posted_to: Optional[date] = Query(None, description="Include jobs posted on or before this date (UTC)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Paginated listings from the ingested global ``jobs`` table with match scores.
    All filters are combined with AND. Skills require every token to match title or description.
    """
    query = db.query(Job)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Job.title.ilike(term),
                Job.company.ilike(term),
                Job.description.ilike(term),
            )
        )
    if company and company.strip():
        query = query.filter(Job.company.ilike(f"%{company.strip()}%"))
    if role and role.strip():
        query = query.filter(Job.title.ilike(f"%{role.strip()}%"))
    if location and location.strip():
        query = query.filter(Job.location.ilike(f"%{location.strip()}%"))

    if skills and skills.strip():
        for part in skills.split(","):
            token = part.strip()
            if not token:
                continue
            st = f"%{token}%"
            query = query.filter(or_(Job.title.ilike(st), Job.description.ilike(st)))

    if experience_levels and experience_levels.strip():
        level_clauses = []
        for level in experience_levels.split(","):
            normalized = level.strip().lower()
            if not normalized:
                continue
            tokens: list[str] = []
            if "entry" in normalized or "junior" in normalized or "new grad" in normalized:
                tokens = ["entry", "junior", "new grad", "graduate", "intern"]
            elif "mid" in normalized:
                tokens = ["mid", "mid-level", "intermediate"]
            elif "senior" in normalized:
                tokens = ["senior", "sr", "sde ii", "sde iii"]
            elif "lead" in normalized or "staff" in normalized:
                tokens = ["lead", "staff", "principal"]
            else:
                tokens = [normalized]

            token_clauses = []
            for token in tokens:
                pattern = f"%{token}%"
                token_clauses.append(or_(Job.title.ilike(pattern), Job.description.ilike(pattern)))
            if token_clauses:
                level_clauses.append(or_(*token_clauses))

        if level_clauses:
            query = query.filter(or_(*level_clauses))

    if job_types and job_types.strip():
        type_clauses = []
        for job_type in job_types.split(","):
            normalized = job_type.strip().lower()
            if not normalized:
                continue
            patterns: list[str] = []
            if "full" in normalized:
                patterns = ["full-time", "full time", "permanent"]
            elif "part" in normalized:
                patterns = ["part-time", "part time"]
            elif "contract" in normalized:
                patterns = ["contract", "contractor"]
            elif "intern" in normalized:
                patterns = ["intern", "internship"]
            else:
                patterns = [normalized]

            per_type_clauses = []
            for pattern in patterns:
                like_pattern = f"%{pattern}%"
                per_type_clauses.append(or_(Job.title.ilike(like_pattern), Job.description.ilike(like_pattern)))
            if per_type_clauses:
                type_clauses.append(or_(*per_type_clauses))

        if type_clauses:
            query = query.filter(or_(*type_clauses))

    if work_modes and work_modes.strip():
        mode_clauses = []
        for mode in work_modes.split(","):
            normalized = mode.strip().lower()
            if not normalized:
                continue
            if "remote" in normalized:
                mode_clauses.append(Job.remote.is_(True))
                continue
            if "onsite" in normalized or "on-site" in normalized:
                mode_clauses.append(Job.remote.is_(False))
                mode_clauses.append(
                    and_(
                        Job.remote.is_(False),
                        Job.location.is_not(None),
                        Job.location.ilike("%onsite%"),
                    )
                )
                continue
            if "hybrid" in normalized:
                hybrid_pattern = "%hybrid%"
                mode_clauses.append(
                    or_(
                        Job.location.ilike(hybrid_pattern),
                        Job.title.ilike(hybrid_pattern),
                        Job.description.ilike(hybrid_pattern),
                    )
                )

        if mode_clauses:
            query = query.filter(or_(*mode_clauses))

    if posted_from is not None:
        query = query.filter(Job.posted_at >= datetime.combine(posted_from, time.min))
    if posted_to is not None:
        query = query.filter(Job.posted_at <= datetime.combine(posted_to, time.max))

    total = query.count()

    rows = (
        query.order_by(desc(Job.posted_at), desc(Job.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    user_profile = db.query(Profile).filter_by(user_id=current_user.id).first()

    items = []
    for row in rows:
        item_dict = JobCorpusItem.model_validate(row).model_dump()
        if user_profile:
            match_data = calculate_job_match(user_profile, row)
            item_dict["match_data"] = match_data
        items.append(item_dict)
    
    return JobCorpusPage(items=items, total=total, page=page, page_size=page_size)
