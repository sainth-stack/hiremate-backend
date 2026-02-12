"""
Chrome extension API routes - autofill data from DB, resume serving, form field mapping.
All endpoints require authentication.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user, get_db
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.schemas.profile import ProfilePayload, profile_model_to_payload
from backend.app.services.form_field_mapper import map_form_fields
from backend.app.services.profile_service import ProfileService

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
    parts = [
        payload.professionalSummary or "",
        f"Headline: {payload.professionalHeadline or ''}",
    ]
    for e in payload.experiences or []:
        parts.append(
            f"{e.jobTitle} at {e.companyName} ({e.startDate}-{e.endDate}): {e.description}"
        )
    for e in payload.educations or []:
        parts.append(f"{e.degree}, {e.institution} ({e.startYear}-{e.endYear})")
    for s in payload.techSkills or []:
        parts.append(f"Skill: {s.name} ({s.level})")
    return "\n\n".join(filter(None, parts))


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


@router.get("/autofill/resume")
def get_resume_file(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the current user's resume file from DB (S3 or local uploads)."""
    try:
        profile = ProfileService.get_or_create_profile(db, current_user)
        resume_url = profile.resume_url
        if not resume_url:
            raise HTTPException(status_code=404, detail="No resume uploaded")

        # S3 / HTTP URL: redirect or proxy
        if resume_url.startswith("http://") or resume_url.startswith("https://"):
            return RedirectResponse(url=resume_url, status_code=302)

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
            return RedirectResponse(url=resume_url, status_code=302)

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
