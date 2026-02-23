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
from backend.app.models.career_page_visit import CareerPageVisit
from backend.app.schemas.profile import ProfilePayload, profile_model_to_payload
from backend.app.services.form_field_mapper import map_form_fields
from backend.app.services.job_description_scraper import parse_job_description_from_html
from backend.app.services.keyword_analyzer import analyze_keywords
from backend.app.services.tailor_context_store import set_tailor_context
from backend.app.services.profile_service import ProfileService, build_resume_text_from_payload

logger = get_logger("api.chrome_extension")
router = APIRouter(prefix="/chrome-extension", tags=["chrome-extension"])


# --- Schemas ---
class AutofillDataOut(BaseModel):
    profile: dict[str, Any]
    custom_answers: dict[str, str]
    resume_text: str
    resume_name: str | None = None  # Display name (same as /resumes, /resume)
    resume_file_name: str | None = None  # Actual filename for fetch URL
    resume_url: str | None = None
    profile_detail: dict[str, Any] | None = None


class FormFieldMapIn(BaseModel):
    fields: list[dict[str, Any]]
    profile: dict[str, Any] | None = None
    custom_answers: dict[str, str] | None = None
    resume_text: str | None = None


class FormFieldMapOut(BaseModel):
    mappings: dict[str, dict[str, Any]]


class KeywordsAnalyzeIn(BaseModel):
    job_description: str | None = None
    page_html: str | None = None  # Client-scraped HTML (extension sends full page)
    url: str | None = None
    resume_text: str | None = None
    resume_id: int | None = None


class ResumeItem(BaseModel):
    id: int
    resume_name: str
    resume_url: str
    is_default: bool
    resume_text: str | None = None


# Canonical application statuses for the tracker
APPLICATION_STATUSES = frozenset({"saved", "applied", "interview", "closed"})


def _normalize_status(raw: str | None) -> str:
    """Map legacy or raw status strings to canonical status."""
    if not raw or not str(raw).strip():
        return "saved"
    s = str(raw).strip().lower()
    legacy_map = {
        "i have not yet applied": "saved",
        "not yet applied": "saved",
        "applied": "applied",
        "interviewing": "interview",
        "offer": "closed",
        "rejected": "closed",
        "withdrawn": "closed",
    }
    return legacy_map.get(s, s if s in APPLICATION_STATUSES else "saved")


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
    application_status: str = "saved"
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
    job_description: str | None = None  # included when url was used (for form prefill)


class TailorContextIn(BaseModel):
    job_description: str | None = None
    job_title: str = ""
    url: str = ""
    page_html: str | None = None  # fallback: parse JD from page if job_description empty


class AutofillTrackIn(BaseModel):
    """Track when user uses autofill on a career/job page."""
    page_url: str
    company_name: str | None = None
    job_url: str | None = None
    job_title: str | None = None


def _profile_to_autofill_format(payload: ProfilePayload) -> dict[str, Any]:
    """Convert ProfilePayload to a UI-friendly profile dict.
    Returns both legacy flat text fields and structured lists for improved UI rendering.
    """
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

    # Build structured experiences list for UI (and keep legacy string)
    experiences_list: list[dict[str, Any]] = []
    exp_parts: list[str] = []
    for e in payload.experiences or []:
        experiences_list.append(
            {
                "jobTitle": e.jobTitle or "",
                "companyName": e.companyName or "",
                "startDate": e.startDate or "",
                "endDate": e.endDate or "",
                "description": e.description or "",
                "location": getattr(e, "location", "") or "",
            }
        )
        exp_parts.append(f"{e.jobTitle} at {e.companyName} ({e.startDate}-{e.endDate}): {e.description}")
    profile["experiences"] = experiences_list
    profile["experience"] = "\n".join(exp_parts) if exp_parts else (payload.professionalSummary or "")

    # Primary company (legacy)
    profile["company"] = ""
    if payload.experiences:
        profile["company"] = payload.experiences[0].companyName or ""

    # Build structured educations list (and keep legacy string)
    educations_list: list[dict[str, Any]] = []
    edu_parts: list[str] = []
    for e in payload.educations or []:
        educations_list.append(
            {
                "degree": e.degree or "",
                "fieldOfStudy": e.fieldOfStudy or "",
                "institution": e.institution or "",
                "startYear": e.startYear or "",
                "endYear": e.endYear or "",
                "grade": getattr(e, "grade", "") or "",
            }
        )
        edu_parts.append(f"{e.degree} in {e.fieldOfStudy}, {e.institution} ({e.startYear}-{e.endYear})")
    profile["educations"] = educations_list
    profile["education"] = "\n".join(edu_parts) if edu_parts else ""

    # Build skills list and keep a comma-separated legacy string
    skills_list: list[str] = []
    for s in payload.techSkills or []:
        skills_list.append(s.name)
    for s in payload.softSkills or []:
        skills_list.append(s.name)
    profile["skills_list"] = skills_list
    profile["skills"] = ", ".join(skills_list) if skills_list else ""

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

    # Resume from single source - same as GET /api/resume
    from backend.app.services.resume_service import list_resumes as list_resumes_svc

    resumes = list_resumes_svc(db, current_user)
    default_resume = resumes[0] if resumes else {}
    resume_name = default_resume.get("resume_name")
    resume_url = default_resume.get("resume_url") or payload.resumeUrl
    resume_text = default_resume.get("resume_text") or _build_resume_text(payload)
    resume_file_name: str | None = None
    if resume_url:
        resume_file_name = (resume_url or "").split("/")[-1].split("?")[0] or None

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
        resume_name=resume_name,
        resume_file_name=resume_file_name,
        resume_url=resume_url,
        profile_detail=payload.model_dump() if payload is not None else None,
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


@router.post("/autofill/track")
def track_autofill(
    payload: AutofillTrackIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Track when user clicks autofill on a career/job page."""
    visit = CareerPageVisit(
        user_id=current_user.id,
        page_url=payload.page_url,
        company_name=payload.company_name,
        job_url=payload.job_url,
        job_title=payload.job_title,
        action_type="autofill_used",
    )
    db.add(visit)
    db.commit()
    logger.info("Autofill tracked user_id=%s page_url=%s", current_user.id, payload.page_url[:80])
    return {"ok": True}


@router.post("/career-page/view")
def track_career_page_view(
    payload: AutofillTrackIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Track when user opens/views a career page."""
    visit = CareerPageVisit(
        user_id=current_user.id,
        page_url=payload.page_url,
        company_name=payload.company_name,
        job_url=payload.job_url,
        job_title=payload.job_title,
        action_type="page_view",
    )
    db.add(visit)
    db.commit()
    logger.info("Career page view tracked user_id=%s page_url=%s", current_user.id, payload.page_url[:80])
    return {"ok": True}


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
    # Attach field type (input/select/textarea/date) so client knows how to fill each field
    out_mappings: dict[str, dict[str, Any]] = {}
    for field in payload.fields or []:
        idx = field.get("index")
        key = str(idx) if (idx is not None and idx != "") else str(field.get("id") or "")
        base = mappings.get(key, {}) or {}
        f_tag = (field.get("tag") or "").lower()
        f_type = (field.get("type") or "").lower()
        inferred = (f_tag or f_type or "input").lower()
        entry = dict(base)
        entry["type"] = inferred
        out_mappings[key] = entry
    for k, v in (mappings or {}).items():
        if k in out_mappings:
            continue
        entry = dict(v or {})
        entry["type"] = entry.get("type") or "input"
        out_mappings[str(k)] = entry
    return FormFieldMapOut(mappings=out_mappings)


@router.get("/resumes", response_model=list[ResumeItem])
def list_user_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResumeItem]:
    """List resumes - delegates to shared resume service (GET /api/resume is preferred)."""
    from backend.app.services.resume_service import list_resumes as list_resumes_svc

    items = list_resumes_svc(db, current_user)
    return [ResumeItem(**it) for it in items]


def _extract_company_from_url(url: str | None) -> str:
    """Extract company name from known ATS URL patterns (Greenhouse, Lever, etc.)."""
    if not url or not url.strip():
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/")
        segments = [s for s in path.split("/") if s]
        host = (parsed.netloc or "").lower()
        if "greenhouse.io" in host and segments:
            return segments[0].replace("-", " ").title()
        if "lever.co" in host and segments:
            return segments[0].replace("-", " ").title()
        if "jobs.workday.com" in host and len(segments) >= 2:
            return segments[0].replace("-", " ").title()
        if "ashbyhq.com" in host and segments:
            return segments[0].replace("-", " ").title()
    except Exception:
        pass
    return ""


def _looks_like_tagline(s: str) -> bool:
    """Detect marketing taglines vs job titles (e.g. 'Best Payment Gateway' vs 'Senior Engineer')."""
    if not s or len(s) < 10:
        return False
    low = s.lower()
    tagline_words = {"best", "payment", "gateway", "online", "financial", "leading", "top", "number", "one"}
    return sum(1 for w in tagline_words if w in low) >= 2 or "gateway" in low or "payment" in low


def _extract_position_from_text(text: str | None) -> str:
    """Extract job title from 'Back to jobs TITLE Location Apply' pattern in job description."""
    if not text or len(text) < 30:
        return ""
    import re
    prefix = text[:500]
    m = re.search(r"Back to jobs\s+(.+?)\s+(?:Apply|Remote|Hybrid|Malaysia|India|Singapore|Bangalore|Kuala Lumpur)", prefix, re.I | re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        if 5 <= len(candidate) <= 80:
            return candidate
    return ""


def _extract_location_from_text(text: str | None) -> str:
    """Extract location like 'City, Country' from job description prefix."""
    if not text or len(text) < 20:
        return ""
    import re
    prefix = text[:1200]
    m = re.search(r"([A-Za-z][A-Za-z\s]{1,40},\s*[A-Za-z\s]{2,35})\s*(?:Apply|Remote|Hybrid|About|Back to)", prefix, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"([A-Za-z][A-Za-z\s]+,\s*[A-Za-z]{2,})\b", prefix)
    if m and len(m.group(1)) < 60:
        return m.group(1).strip()
    return ""


@router.post("/jobs")
def save_job(
    payload: JobSaveIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save job to user's tracker. Derives company from URL when empty. Single commit for speed."""
    status = _normalize_status(payload.application_status)
    company = (payload.company or "").strip()
    if not company and payload.job_posting_url:
        company = _extract_company_from_url(payload.job_posting_url)

    position_title = (payload.position_title or "").strip()
    if position_title and _looks_like_tagline(position_title) and payload.job_description:
        extracted = _extract_position_from_text(payload.job_description)
        if extracted:
            position_title = extracted

    location = (payload.location or "").strip()
    if not location and payload.job_description:
        location = _extract_location_from_text(payload.job_description)

    job = UserJob(
        user_id=current_user.id,
        company=company or None,
        position_title=position_title or None,
        location=location or None,
        min_salary=payload.min_salary,
        max_salary=payload.max_salary,
        currency=payload.currency,
        period=payload.period,
        job_type=payload.job_type,
        job_description=payload.job_description,
        notes=payload.notes,
        application_status=status,
        job_posting_url=payload.job_posting_url,
    )
    db.add(job)
    db.flush()

    page_url = payload.job_posting_url or ""
    if not page_url and company:
        page_url = f"https://{company.lower().replace(' ', '')}.com/careers"
    if not page_url:
        page_url = "unknown"
    visit = CareerPageVisit(
        user_id=current_user.id,
        page_url=page_url,
        company_name=company or None,
        job_url=payload.job_posting_url,
        job_title=payload.position_title,
        action_type="save_job",
    )
    db.add(visit)
    db.commit()
    db.refresh(job)

    logger.info("Job saved user_id=%s job_id=%s company=%s", current_user.id, job.id, job.company)
    return {"id": job.id, "message": "Job saved successfully"}


# Statuses that count as "applied" for dashboard (past saved stage)
APPLIED_STATUSES = frozenset({"applied", "interview", "closed"})


@router.get("/jobs")
def list_user_jobs(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List user's saved jobs. Optional ?status=applied to filter to applied/interview/closed only."""
    q = db.query(UserJob).filter(UserJob.user_id == current_user.id).order_by(UserJob.created_at.desc())
    if status == "applied":
        # Include legacy + new statuses for backwards compat
        legacy = frozenset({"Applied", "Interviewing", "Offer", "Rejected", "Withdrawn"})
        q = q.filter(UserJob.application_status.in_(APPLIED_STATUSES | legacy))
    jobs = q.all()
    return [
        {
            "id": j.id,
            "company": j.company or "",
            "position_title": j.position_title or "",
            "location": j.location or "",
            "application_status": _normalize_status(j.application_status),
            "job_posting_url": j.job_posting_url,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


class JobUpdateIn(BaseModel):
    application_status: str | None = None


@router.patch("/jobs/{job_id}")
def update_user_job(
    job_id: int,
    payload: JobUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update job status (saved, applied, interview, closed)."""
    job = db.query(UserJob).filter(UserJob.id == job_id, UserJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if payload.application_status is not None:
        job.application_status = _normalize_status(payload.application_status)
    db.commit()
    db.refresh(job)
    return {"id": job.id, "message": "Job updated"}


@router.post("/keywords/analyze", response_model=KeywordsAnalyzeOut)
async def analyze_job_keywords(
    payload: KeywordsAnalyzeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KeywordsAnalyzeOut:
    """Extract keywords from job description, match against resume. Extension sends page_html from DOM."""
    job_description = payload.job_description
    if (not job_description or len(job_description) < 50) and payload.page_html and len(payload.page_html.strip()) > 100:
        job_description = parse_job_description_from_html(payload.page_html) or ""

    if not job_description or len(job_description) < 50:
        detail = (
            "Could not find job requirements on this page. The content may be salary/benefits only. "
            "Scroll down for the full job description or click through to the complete posting."
            if payload.page_html and len(payload.page_html.strip()) > 500
            else "job_description or page_html with scrapable content is required"
        )
        raise HTTPException(status_code=400, detail=detail)

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
    out = KeywordsAnalyzeOut(**result)
    out.job_description = job_description  # include for form prefill
    return out


@router.post("/tailor-context")
def save_tailor_context(
    payload: TailorContextIn,
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Store job description + title for Tailor Resume flow.
    Extension calls this before opening /resume-generator; that page fetches via GET /resume/tailor-context.
    """
    job_description = (payload.job_description or "").strip()
    if (not job_description or len(job_description) < 50) and payload.page_html and len((payload.page_html or "").strip()) > 100:
        job_description = parse_job_description_from_html(payload.page_html) or ""
    job_description = (job_description or "").strip()
    if not job_description or len(job_description) < 50:
        raise HTTPException(status_code=400, detail="job_description or page_html with scrapable content is required")
    set_tailor_context(
        user_id=current_user.id,
        job_description=job_description,
        job_title=(payload.job_title or "").strip(),
        url=(payload.url or "").strip(),
    )
    return {"ok": True}


# --- Cover Letter ---
class CoverLetterGenerateIn(BaseModel):
    job_description: str = ""
    job_title: str = ""


@router.get("/cover-letter")
def get_cover_letter(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get stored cover letter from profile preferences."""
    profile = ProfileService.get_or_create_profile(db, current_user)
    prefs = profile.preferences or {}
    cl = prefs.get("cover_letter") or {}
    if isinstance(cl, dict):
        return {
            "content": cl.get("content") or "",
            "job_title": cl.get("job_title") or "",
            "job_url": cl.get("job_url") or "",
        }
    return {"content": "", "job_title": "", "job_url": ""}


@router.post("/cover-letter/generate")
def generate_cover_letter_endpoint(
    payload: CoverLetterGenerateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate cover letter from profile + JD, store in preferences, return content."""
    from backend.app.services.cover_letter_service import generate_cover_letter as gen_cover

    profile = ProfileService.get_or_create_profile(db, current_user)
    pl = profile_model_to_payload(profile)
    content = gen_cover(
        pl,
        job_title=payload.job_title or "",
        job_description=payload.job_description or "",
    )
    prefs = dict(profile.preferences or {})
    prefs["cover_letter"] = {
        "content": content or "",
        "job_title": (payload.job_title or "").strip(),
        "job_description": (payload.job_description or "")[:500],
        "updated_at": None,
    }
    profile.preferences = prefs
    db.commit()
    return {
        "content": content or "",
        "job_title": (payload.job_title or "").strip(),
    }
