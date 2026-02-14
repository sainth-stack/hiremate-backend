"""
Chrome extension API routes - autofill data from DB, resume serving, form field mapping.
All endpoints require authentication.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user, get_db
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.models.user_resume import UserResume
from backend.app.models.user_job import UserJob
from backend.app.schemas.profile import ProfilePayload, profile_model_to_payload
from backend.app.services.form_field_mapper import map_form_fields
from backend.app.services.job_description_scraper import scrape_job_description_async
from backend.app.services.keyword_analyzer import analyze_keywords
from backend.app.services.profile_service import ProfileService, build_resume_text_from_payload

logger = get_logger("api.chrome_extension")
router = APIRouter(prefix="/chrome-extension", tags=["chrome-extension"])


# --- Schemas ---
class AutofillDataOut(BaseModel):
    profile: dict[str, Any]
    custom_answers: dict[str, str]
    resume_text: str
    resume_file_name: str | None = None
    resume_url: str | None = None


class FormFieldMapIn(BaseModel):
    fields: list[dict[str, Any]]
    profile: dict[str, Any] | None = None
    custom_answers: dict[str, str] | None = None
    resume_text: str | None = None


class FormFieldMapOut(BaseModel):
    mappings: dict[str, dict[str, Any]]


class KeywordsAnalyzeIn(BaseModel):
    job_description: str | None = None
    url: str | None = None
    resume_text: str | None = None
    resume_id: int | None = None


class JobDescriptionScrapeIn(BaseModel):
    url: str


class JobDescriptionScrapeOut(BaseModel):
    job_description: str | None = None


class ResumeItem(BaseModel):
    id: int
    resume_name: str
    resume_url: str
    is_default: bool
    resume_text: str | None = None


class JobSaveIn(BaseModel):
    company: str = ""
    position_title: str = ""
    location: str = ""
    min_salary: str | None = None
    max_salary: str | None = None
    currency: str = "USD"
    period: str = "Yearly"
    job_type: str = "Full-Time"
    job_description: str | None = None
    notes: str | None = None
    application_status: str = "I have not yet applied"
    job_posting_url: str | None = None


class KeywordItem(BaseModel):
    keyword: str
    matched: bool


class KeywordsAnalyzeOut(BaseModel):
    total_keywords: int
    matched_count: int
    percent: int
    high_priority: list[KeywordItem]
    low_priority: list[KeywordItem]
    message: str | None = None


def _profile_to_autofill_format(payload: ProfilePayload) -> dict[str, Any]:
    """Convert ProfilePayload to flat profile dict expected by form_field_mapper."""
    profile: dict[str, Any] = {
        "firstName": payload.firstName or "",
        "lastName": payload.lastName or "",
        "name": f"{payload.firstName} {payload.lastName}".strip() or "",
        "email": payload.email or "",
        "phone": payload.phone or "",
        "city": payload.city or "",
        "country": payload.country or "",
        "location": ", ".join(filter(None, [payload.city, payload.country])),
        "linkedin": payload.links.linkedInUrl if payload.links else "",
        "github": payload.links.githubUrl if payload.links else "",
        "portfolio": payload.links.portfolioUrl if payload.links else "",
        "title": payload.professionalHeadline or "",
        "professionalHeadline": payload.professionalHeadline or "",
        "professionalSummary": payload.professionalSummary or "",
        "expectedSalary": payload.preferences.expectedSalaryRange if payload.preferences else "",
        "willingToRelocate": payload.preferences.willingToRelocate if payload.preferences else "",
        "openToRemote": payload.preferences.openToRemote if payload.preferences else "",
    }
    # Build experience string from experiences
    exp_parts = []
    for e in payload.experiences or []:
        exp_parts.append(
            f"{e.jobTitle} at {e.companyName} ({e.startDate}-{e.endDate}): {e.description}"
        )
    profile["experience"] = "\n".join(exp_parts) if exp_parts else (payload.professionalSummary or "")
    profile["company"] = ""
    if payload.experiences:
        profile["company"] = payload.experiences[0].companyName or ""
    # Build education string
    edu_parts = []
    for e in payload.educations or []:
        edu_parts.append(f"{e.degree} in {e.fieldOfStudy}, {e.institution} ({e.startYear}-{e.endYear})")
    profile["education"] = "\n".join(edu_parts) if edu_parts else ""
    # Build skills string
    skills = []
    for s in payload.techSkills or []:
        skills.append(s.name)
    for s in payload.softSkills or []:
        skills.append(s.name)
    profile["skills"] = ", ".join(skills) if skills else ""
    return profile


def _build_resume_text(payload: ProfilePayload) -> str:
    """Build resume text from profile for LLM context."""
    return build_resume_text_from_payload(payload)


@router.get("/autofill/data", response_model=AutofillDataOut)
def get_autofill_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AutofillDataOut:
    """Load autofill data from user's profile in DB."""
    try:
        profile = ProfileService.get_or_create_profile(db, current_user)
        payload = profile_model_to_payload(profile)
    except Exception as exc:
        logger.exception("Failed to load profile for autofill")
        raise HTTPException(status_code=500, detail=f"Failed to load profile: {exc}") from exc

    autofill_profile = _profile_to_autofill_format(payload)
    resume_text = _build_resume_text(payload)

    # Resume file: extract filename from URL for local, or use URL for S3
    resume_url = payload.resumeUrl
    resume_file_name: str | None = None
    if resume_url:
        if resume_url.startswith("http"):
            resume_file_name = resume_url.split("/")[-1] if "/" in resume_url else None
        else:
            resume_file_name = Path(resume_url).name if resume_url else None

    logger.info(
        "Autofill data loaded user_id=%s profile_keys=%d resume_text_len=%d resume=%s",
        current_user.id,
        len(autofill_profile),
        len(resume_text),
        resume_file_name or resume_url,
    )

    return AutofillDataOut(
        profile=autofill_profile,
        custom_answers={},
        resume_text=resume_text,
        resume_file_name=resume_file_name,
        resume_url=resume_url,
    )


def _guess_media_type(filename: str) -> str:
    """Guess media type from filename extension."""
    ext = Path(filename).suffix.lower()
    mime = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".rtf": "application/rtf",
    }
    return mime.get(ext, "application/pdf")


@router.get("/autofill/resume")
def get_resume_file(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the current user's resume file from DB (S3 or local uploads). Proxies S3 URLs to avoid CORS."""
    try:
        profile = ProfileService.get_or_create_profile(db, current_user)
        resume_url = profile.resume_url
        if not resume_url:
            raise HTTPException(status_code=404, detail="No resume uploaded")

        # S3 / HTTP URL: proxy through backend to avoid CORS when extension fetches from job sites
        if resume_url.startswith("http://") or resume_url.startswith("https://"):
            try:
                with urlopen(resume_url, timeout=30) as resp:
                    data = resp.read()
                filename = resume_url.split("/")[-1].split("?")[0] or "resume.pdf"
                media_type = _guess_media_type(filename)
                logger.info("Proxied resume from S3 user_id=%s bytes=%d", current_user.id, len(data))
                return Response(content=data, media_type=media_type, headers={"Content-Disposition": f'inline; filename="{filename}"'})
            except Exception as exc:
                logger.exception("Failed to proxy resume from %s", resume_url)
                raise HTTPException(status_code=502, detail=f"Failed to fetch resume: {exc}") from exc

        # Local path: /uploads/resumes/filename.pdf
        safe_name = Path(resume_url).name
        # Resolve upload dir - main.py uses Path(settings.upload_dir)
        upload_base = Path(settings.upload_dir)
        if not upload_base.is_absolute():
            upload_base = Path.cwd() / upload_base
        resume_path = upload_base / safe_name
        if not resume_path.exists():
            raise HTTPException(status_code=404, detail="Resume file not found")
        logger.info("Serving resume file user_id=%s file=%s", current_user.id, safe_name)
        return FileResponse(resume_path, media_type="application/pdf", filename=safe_name)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to serve resume file")
        raise HTTPException(status_code=500, detail=f"Failed to load resume: {exc}") from exc


@router.get("/autofill/resume/{file_name}")
def get_resume_file_by_name(
    file_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve resume by filename (for compatibility when extension passes filename from autofill/data)."""
    try:
        profile = ProfileService.get_or_create_profile(db, current_user)
        resume_url = profile.resume_url
        if not resume_url:
            raise HTTPException(status_code=404, detail="No resume uploaded")

        safe_name = Path(file_name).name
        if safe_name not in resume_url and Path(resume_url).name != safe_name:
            raise HTTPException(status_code=404, detail="Resume file not found")

        if resume_url.startswith("http"):
            try:
                with urlopen(resume_url, timeout=30) as resp:
                    data = resp.read()
                media_type = _guess_media_type(safe_name)
                return Response(content=data, media_type=media_type, headers={"Content-Disposition": f'inline; filename="{safe_name}"'})
            except Exception as exc:
                logger.exception("Failed to proxy resume from %s", resume_url)
                raise HTTPException(status_code=502, detail=f"Failed to fetch resume: {exc}") from exc

        upload_base = Path(settings.upload_dir)
        if not upload_base.is_absolute():
            upload_base = Path.cwd() / upload_base
        resume_path = upload_base / safe_name
        if not resume_path.exists():
            resume_path = upload_base / Path(resume_url).name
        if not resume_path.exists():
            raise HTTPException(status_code=404, detail="Resume file not found")
        return FileResponse(resume_path, media_type="application/pdf", filename=safe_name)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to serve resume file")
        raise HTTPException(status_code=500, detail=f"Failed to load resume: {exc}") from exc


@router.post("/form-fields/map", response_model=FormFieldMapOut)
def map_fields(
    payload: FormFieldMapIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FormFieldMapOut:
    """Map form fields to profile values using LLM + heuristics."""
    if not payload.fields:
        raise HTTPException(status_code=400, detail="fields are required")

    profile = payload.profile or {}
    custom_answers = payload.custom_answers or {}
    resume_text = payload.resume_text or ""

    if not profile and not custom_answers:
        profile_obj = ProfileService.get_or_create_profile(db, current_user)
        pl = profile_model_to_payload(profile_obj)
        profile = _profile_to_autofill_format(pl)
        resume_text = resume_text or _build_resume_text(pl)

    logger.info(
        "Form map request user_id=%s fields=%d profile_keys=%d custom_answers=%d resume_text_len=%d",
        current_user.id,
        len(payload.fields),
        len(profile),
        len(custom_answers),
        len(resume_text),
    )

    try:
        mappings = map_form_fields(
            fields=payload.fields,
            profile=profile,
            custom_answers=custom_answers,
            resume_text=resume_text,
        )
    except Exception as exc:
        logger.exception("Failed to map form fields")
        raise HTTPException(status_code=500, detail=f"Mapping failed: {exc}") from exc

    logger.info("Form map response mappings=%d", len(mappings))
    return FormFieldMapOut(mappings=mappings)


@router.get("/resumes", response_model=list[ResumeItem])
def list_user_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResumeItem]:
    """List user's resumes for keyword analyser dropdown. Includes profile resume as fallback."""
    resumes: list[ResumeItem] = []
    db_resumes = db.query(UserResume).filter(UserResume.user_id == current_user.id).order_by(UserResume.is_default.desc(), UserResume.created_at.desc()).all()
    for r in db_resumes:
        resumes.append(
            ResumeItem(
                id=r.id,
                resume_name=r.resume_name,
                resume_url=r.resume_url,
                is_default=bool(r.is_default),
                resume_text=r.resume_text,
            )
        )
    if not resumes:
        profile = ProfileService.get_or_create_profile(db, current_user)
        pl = profile_model_to_payload(profile)
        resume_text = _build_resume_text(pl)
        resume_url = pl.resumeUrl or ""
        if resume_url or resume_text:
            name = "Default resume"
            if resume_url:
                name = Path(resume_url).name.split("?")[0] or name
            resumes.append(
                ResumeItem(
                    id=0,
                    resume_name=name + (" (default)" if resume_url else ""),
                    resume_url=resume_url or "",
                    is_default=True,
                    resume_text=resume_text,
                )
            )
    return resumes


@router.post("/jobs")
def save_job(
    payload: JobSaveIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save job to user's tracker (Edit Job Description form)."""
    job = UserJob(
        user_id=current_user.id,
        company=payload.company,
        position_title=payload.position_title,
        location=payload.location,
        min_salary=payload.min_salary,
        max_salary=payload.max_salary,
        currency=payload.currency,
        period=payload.period,
        job_type=payload.job_type,
        job_description=payload.job_description,
        notes=payload.notes,
        application_status=payload.application_status,
        job_posting_url=payload.job_posting_url,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Job saved user_id=%s job_id=%s company=%s", current_user.id, job.id, job.company)
    return {"id": job.id, "message": "Job saved successfully"}


@router.post("/job-description/scrape", response_model=JobDescriptionScrapeOut)
async def scrape_job_description_endpoint(
    payload: JobDescriptionScrapeIn,
    current_user: User = Depends(get_current_user),
) -> JobDescriptionScrapeOut:
    """Scrape job description from URL using Playwright (handles JS-heavy sites)."""
    if not payload.url or not payload.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Valid url is required")
    job_description = await scrape_job_description_async(payload.url)
    return JobDescriptionScrapeOut(job_description=job_description)


@router.post("/keywords/analyze", response_model=KeywordsAnalyzeOut)
async def analyze_job_keywords(
    payload: KeywordsAnalyzeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KeywordsAnalyzeOut:
    """Extract keywords from job description, match against resume, return analysis.
    If url is provided, scrapes job description via Playwright first (for JS-heavy sites)."""
    job_description = payload.job_description
    if (not job_description or len(job_description) < 50) and payload.url:
        job_description = (await scrape_job_description_async(payload.url)) or ""

    if not job_description or len(job_description) < 50:
        raise HTTPException(status_code=400, detail="job_description or url with scrapable content is required")

    resume_text = payload.resume_text
    if payload.resume_id is not None and payload.resume_id > 0:
        ur = db.query(UserResume).filter(UserResume.id == payload.resume_id, UserResume.user_id == current_user.id).first()
        if ur and ur.resume_text:
            resume_text = ur.resume_text
    if not resume_text:
        profile = ProfileService.get_or_create_profile(db, current_user)
        pl = profile_model_to_payload(profile)
        resume_text = _build_resume_text(pl)

    result = analyze_keywords(
        job_description=job_description,
        resume_text=resume_text or "",
    )
    return KeywordsAnalyzeOut(**result)
