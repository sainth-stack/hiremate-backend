"""
Chrome extension API routes - autofill data from DB, resume serving, form field mapping.
All endpoints require authentication.
"""
from __future__ import annotations

import logging
from datetime import datetime
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
from backend.app.models.form_field_learning import (
    UserFieldAnswer,
    SharedFieldProfileKey,
    SharedSelectorPerformance,
    SharedFormStructure,
    UserSubmissionHistory,
)
from backend.app.schemas.profile import ProfilePayload, profile_model_to_payload
from backend.app.services.form_field_mapper import map_form_fields, map_form_fields_llm_for_misses
from backend.app.utils.fingerprint import compute_field_fingerprint, normalize_label
from backend.app.services.job_description_scraper import parse_job_description_from_html
from backend.app.services.keyword_analyzer import analyze_keywords
from backend.app.services.tailor_context_store import set_tailor_context
from backend.app.services.profile_service import ProfileService, build_resume_text_from_payload

logger = get_logger("api.chrome_extension")
router = APIRouter(prefix="/chrome-extension", tags=["chrome-extension"])


# --- Schemas ---
class AutofillContextOut(BaseModel):
    profile: dict[str, Any]
    resume_text: str
    resume_url: str | None = None
    resume_name: str | None = None
    custom_answers: dict[str, str]


class FormFieldMapIn(BaseModel):
    fields: list[dict[str, Any]]
    profile: dict[str, Any] | None = None
    custom_answers: dict[str, str] | None = None
    resume_text: str | None = None


class FormFieldMapOut(BaseModel):
    mappings: dict[str, dict[str, Any]]
    unfilled_profile_keys: list[str] | None = None


class SubmitFeedbackFieldIn(BaseModel):
    fingerprint: str
    label: str | None = None
    type: str | None = None
    options: list[str] | None = None
    ats_platform: str | None = None
    selector_used: str | None = None
    selector_type: str | None = None
    autofill_value: str | None = None
    submitted_value: str | None = None
    was_edited: bool = False


class SubmitFeedbackIn(BaseModel):
    url: str = ""
    domain: str = ""
    ats: str | None = None
    fields: list[SubmitFeedbackFieldIn] = []


class SelectorBatchIn(BaseModel):
    fps: list[str] = []
    ats_platform: str | None = None


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


class ExtensionErrorIn(BaseModel):
    """Extension error report for monitoring/analytics."""
    type: str = ""
    message: str = ""
    context: str | None = None
    stack: str | None = None
    source: str | None = None
    line: int | None = None
    column: int | None = None
    extensionVersion: str | None = None
    userAgent: str | None = None
    url: str | None = None
    environment: str | None = None
    timestamp: int | None = None


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


@router.get("/autofill/context", response_model=AutofillContextOut)
async def get_autofill_context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AutofillContextOut:
    """
    Merged autofill: profile + resume text + resume URL.
    Cached 300s per user. resume_url points to /autofill/resume/{filename} for PDF fetch.
    """
    from backend.app.utils import cache

    user_id = current_user.id
    cache_key = f"autofill_ctx:{user_id}"

    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            return AutofillContextOut(**cached)
    except Exception:
        pass

    try:
        profile = ProfileService.get_or_create_profile(db, current_user)
        payload = profile_model_to_payload(profile)
    except Exception as exc:
        logger.exception("Failed to load profile for autofill")
        raise HTTPException(status_code=500, detail=f"Failed to load profile: {exc}") from exc

    autofill_profile = _profile_to_autofill_format(payload)

    from backend.app.services.resume_service import list_resumes as list_resumes_svc

    resumes = list_resumes_svc(db, current_user)
    default_resume = resumes[0] if resumes else {}
    resume_text = default_resume.get("resume_text") or _build_resume_text(payload)
    resume_url: str | None = default_resume.get("resume_url") or payload.resumeUrl
    resume_name: str | None = default_resume.get("resume_name")
    # Resolve backend proxy URL for extension (avoids S3 CORS). Always use /autofill/resume/{filename}.
    if resume_url:
        fn = (resume_url or "").split("/")[-1].split("?")[0] or "resume.pdf"
        resume_url = f"/api/chrome-extension/autofill/resume/{fn}"

    out = AutofillContextOut(
        profile=autofill_profile,
        resume_text=resume_text,
        resume_url=resume_url,
        resume_name=resume_name,
        custom_answers={},
    )

    try:
        await cache.set(cache_key, out.model_dump(), ttl=settings.autofill_context_cache_ttl)
    except Exception:
        pass

    logger.info(
        "Autofill context loaded user_id=%s profile_keys=%d resume_text_len=%d",
        current_user.id,
        len(autofill_profile),
        len(resume_text),
    )
    return out


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
                with urlopen(resume_url, timeout=settings.http_request_timeout) as resp:
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


def _get_profile_for_map(payload: FormFieldMapIn, db: Session, current_user: User) -> tuple[dict[str, Any], str]:
    """Get profile dict and resume_text for form mapping."""
    profile = payload.profile or {}
    resume_text = payload.resume_text or ""
    if not profile and not payload.custom_answers:
        profile_obj = ProfileService.get_or_create_profile(db, current_user)
        pl = profile_model_to_payload(profile_obj)
        profile = _profile_to_autofill_format(pl)
        resume_text = resume_text or _build_resume_text(pl)
    return profile, resume_text


def _persist_llm_results(
    db: Session,
    user_id: int,
    fields: list[dict[str, Any]],
    llm_results: dict[str, dict[str, Any]],
    profile: dict[str, Any],
    ats_platform: str = "unknown",
) -> None:
    """Persist LLM results to user_field_answers and shared_field_profile_keys. Keyed by field_fp."""
    from sqlalchemy import func

    # Dedupe by field_fp: repeated form fields (e.g. Degree x3) share same fp; only persist once per fp
    seen_fps: dict[str, tuple[dict, dict]] = {}
    for field in fields:
        fp = field.get("_fp")
        if not fp or fp in seen_fps:
            continue
        res = llm_results.get(fp, {})
        val = res.get("value")
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        seen_fps[fp] = (field, res)

    seen_shared_fps: set[str] = set()
    for fp, (field, res) in seen_fps.items():
        value = res.get("value")
        if value is None:
            continue
        profile_key = res.get("profile_key")
        confidence = float(res.get("confidence", 0.8))
        label_norm = (normalize_label(field.get("label", "")) or "")[:255]

        existing = db.query(UserFieldAnswer).filter_by(user_id=user_id, field_fp=fp).first()
        if existing:
            existing.value = value
            existing.source = "llm"
            existing.confidence = confidence
            existing.label_norm = label_norm
            existing.last_used = func.now()
            existing.used_count = (existing.used_count or 0) + 1
        else:
            db.add(UserFieldAnswer(
                user_id=user_id,
                field_fp=fp,
                label_norm=label_norm,
                value=value,
                source="llm",
                confidence=confidence,
            ))

        if profile_key and profile_key != "null" and fp not in seen_shared_fps:
            from backend.app.services.form_field_mapper import PROFILE_KEY_TO_FIELD
            pf_key = PROFILE_KEY_TO_FIELD.get(profile_key, profile_key)
            if pf_key in profile and profile.get(pf_key):
                seen_shared_fps.add(fp)
                existing_shared = db.query(SharedFieldProfileKey).filter_by(field_fp=fp).first()
                if existing_shared:
                    existing_shared.vote_count = (existing_shared.vote_count or 0) + 1
                    existing_shared.confidence = max(existing_shared.confidence or 0.5, confidence)
                else:
                    db.add(SharedFieldProfileKey(
                        field_fp=fp,
                        ats_platform=ats_platform,
                        label_norm=label_norm,
                        profile_key=profile_key,
                        confidence=confidence,
                        vote_count=1,
                    ))
    db.commit()


def _compute_unfilled_keys(
    fields: list[dict[str, Any]],
    user_map: dict[str, Any],
) -> list[str]:
    """Return labels of fields that weren't filled (for profile gap tooltip)."""
    unfilled = []
    for f in fields:
        fp = f.get("_fp")
        if fp and fp not in user_map:
            unfilled.append(normalize_label(f.get("label", "")))
    return unfilled


@router.post("/form-fields/map", response_model=FormFieldMapOut)
def map_fields(
    payload: FormFieldMapIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FormFieldMapOut:
    """Map form fields using 4-layer resolution: user cache, shared profile keys, LLM."""
    if not payload.fields:
        raise HTTPException(status_code=400, detail="fields are required")

    profile, resume_text = _get_profile_for_map(payload, db, current_user)
    custom_answers = payload.custom_answers or {}
    ats_platform = (payload.fields[0].get("platform") if payload.fields else None) or "unknown"

    # Compute fingerprints for each field
    fields_with_fp = []
    for f in payload.fields:
        fc = dict(f)
        fc["_fp"] = compute_field_fingerprint(fc)
        fields_with_fp.append(fc)
    fps = [f["_fp"] for f in fields_with_fp]

    # Layer 2: Per-user learned answers (DB)
    user_rows = (
        db.query(UserFieldAnswer)
        .filter_by(user_id=current_user.id)
        .filter(UserFieldAnswer.field_fp.in_(fps))
        .all()
    )
    user_map = {r.field_fp: r.value for r in user_rows if (r.value or "").strip()}

    # Layer 3: Shared profile key lookup
    miss_fps = [fp for fp in fps if fp not in user_map]
    if miss_fps:
        from backend.app.services.form_field_mapper import PROFILE_KEY_TO_FIELD
        shared_rows = (
            db.query(SharedFieldProfileKey)
            .filter(SharedFieldProfileKey.field_fp.in_(miss_fps))
            .all()
        )
        for row in shared_rows:
            pk = PROFILE_KEY_TO_FIELD.get(row.profile_key, row.profile_key)
            if pk in profile and profile.get(pk):
                user_map[row.field_fp] = profile.get(pk)

    # Layer 4: LLM for remaining misses
    llm_fields = [f for f in fields_with_fp if f["_fp"] not in user_map]
    llm_results: dict[str, dict[str, Any]] = {}
    if llm_fields:
        try:
            llm_results = map_form_fields_llm_for_misses(
                fields_with_fp=llm_fields,
                profile=profile,
                custom_answers=custom_answers,
                resume_text=resume_text,
            )
            for fp, res in llm_results.items():
                val = res.get("value")
                if val is not None and (not isinstance(val, str) or val.strip()):
                    user_map[fp] = val
            _persist_llm_results(db, current_user.id, llm_fields, llm_results, profile, ats_platform)
        except Exception as exc:
            logger.exception("LLM mapping failed")
            raise HTTPException(status_code=500, detail=f"Mapping failed: {exc}") from exc

    unfilled_keys = _compute_unfilled_keys(fields_with_fp, user_map)

    # Build response: mappings by fingerprint (primary) and by index (backward compat)
    out_mappings: dict[str, dict[str, Any]] = {}
    for field in fields_with_fp:
        fp = field["_fp"]
        idx = field.get("index")
        key_idx = str(idx) if (idx is not None and idx != "") else str(field.get("id") or "")
        value = user_map.get(fp)
        f_tag = (field.get("tag") or "").lower()
        f_type = (field.get("type") or "").lower()
        inferred = (f_tag or f_type or "input").lower()
        entry = {"value": value, "confidence": 0.9, "reason": "", "type": inferred}
        out_mappings[fp] = entry
        out_mappings[key_idx] = entry

    logger.info(
        "Form map: user_id=%s fields=%d hits=%d llm=%d",
        current_user.id,
        len(fields_with_fp),
        len(user_map),
        len(llm_results),
    )
    return FormFieldMapOut(mappings=out_mappings, unfilled_profile_keys=unfilled_keys)


def _update_form_structure(
    db: Session,
    domain: str,
    url: str,
    ats: str | None,
    fields: list,
) -> None:
    """Upsert shared_form_structures with field fingerprints from submission."""
    from datetime import datetime

    fps = [f.fingerprint for f in fields if getattr(f, "fingerprint", None)]
    if not fps:
        return
    ats = ats or "unknown"
    url_pattern = (url or "")[:200] if url else ""
    row = db.query(SharedFormStructure).filter_by(domain=domain).first()
    if row:
        row.field_fps = list(set((row.field_fps or []) + fps))
        row.field_count = len(row.field_fps)
        row.sample_count = (row.sample_count or 0) + 1
        row.confidence = min((row.sample_count or 1) / 10.0, 1.0)
        row.last_seen = datetime.utcnow()
        row.ats_platform = ats
    else:
        db.add(SharedFormStructure(
            domain=domain,
            url_pattern=url_pattern,
            ats_platform=ats,
            field_count=len(fps),
            field_fps=fps,
            sample_count=1,
            confidence=0.1,
            last_seen=datetime.utcnow(),
        ))
    db.commit()


@router.post("/form-fields/submit-feedback")
def submit_feedback(
    payload: SubmitFeedbackIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Learn from form submission - user answers, selector performance."""
    from datetime import datetime
    from sqlalchemy import func

    submission_record = []
    for field in payload.fields:
        fp = field.fingerprint
        value = field.submitted_value if field.submitted_value is not None else field.autofill_value
        if not fp:
            continue
        if value is None:
            continue
        source = "form_submit"
        conf = 1.0 if not field.was_edited else 0.95
        if field.was_edited:
            source = "user_edit"

        existing = db.query(UserFieldAnswer).filter_by(user_id=current_user.id, field_fp=fp).first()
        if existing:
            existing.value = value
            existing.source = source
            existing.confidence = conf
            existing.last_used = func.now()
            existing.used_count = (existing.used_count or 0) + 1
        else:
            label_norm = (normalize_label(field.label or "") or "")[:255]
            db.add(UserFieldAnswer(
                user_id=current_user.id,
                field_fp=fp,
                label_norm=label_norm,
                value=value,
                source=source,
                confidence=conf,
            ))

        if field.selector_used and (field.ats_platform or payload.ats):
            ats = field.ats_platform or payload.ats or "unknown"
            sel_type = field.selector_type or "id"
            sel_row = (
                db.query(SharedSelectorPerformance)
                .filter_by(field_fp=fp, ats_platform=ats, selector_type=sel_type, selector=field.selector_used)
                .first()
            )
            if sel_row:
                sel_row.success_count = (sel_row.success_count or 0) + 1
                sel_row.last_success = datetime.utcnow()
            else:
                db.add(SharedSelectorPerformance(
                    field_fp=fp,
                    ats_platform=ats,
                    selector_type=sel_type,
                    selector=field.selector_used,
                    success_count=1,
                    last_success=datetime.utcnow(),
                ))

        submission_record.append({
            "field_fp": fp,
            "label": field.label,
            "value": value,
            "source": source,
            "was_edited": field.was_edited,
        })

    db.add(UserSubmissionHistory(
        user_id=current_user.id,
        domain=payload.domain,
        url=payload.url,
        ats_platform=payload.ats or "unknown",
        field_count=len(payload.fields),
        filled_count=len([f for f in payload.fields if f.submitted_value]),
        submitted_fields=submission_record,
    ))
    _update_form_structure(db, payload.domain, payload.url, payload.ats, payload.fields)
    db.commit()
    return {"ok": True, "learned": len(submission_record)}


@router.get("/form-structure/check")
def check_form_structure(
    domain: str = "",
    url: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return known form structure + best selectors for fast scrape path."""
    if not domain:
        return {"found": False}
    row = (
        db.query(SharedFormStructure)
        .filter_by(domain=domain)
        .order_by(SharedFormStructure.sample_count.desc())
        .first()
    )
    if not row:
        return {"found": False}

    fps = row.field_fps or []
    selector_rows = (
        db.query(SharedSelectorPerformance)
        .filter(SharedSelectorPerformance.field_fp.in_(fps))
        .filter_by(ats_platform=row.ats_platform or "unknown")
        .filter(SharedSelectorPerformance.success_count >= 3)
        .all()
    )
    best_selectors = {}
    for s in selector_rows:
        if s.field_fp not in best_selectors or (s.success_count or 0) > best_selectors[s.field_fp].get("success_count", 0):
            best_selectors[s.field_fp] = {
                "selector": s.selector,
                "type": s.selector_type,
                "success_count": s.success_count or 0,
            }
    confidence = min((row.sample_count or 1) / 10.0, 1.0)
    return {
        "found": True,
        "field_fps": fps,
        "ats_platform": row.ats_platform,
        "confidence": confidence,
        "best_selectors": best_selectors,
        "is_multi_step": row.is_multi_step or False,
        "step_count": row.step_count or 1,
    }


@router.post("/selectors/best-batch")
def best_selectors_batch(
    payload: SelectorBatchIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return best selectors for given fingerprints + ATS."""
    if not payload.fps:
        return {"selectors": {}}
    ats = payload.ats_platform or "unknown"
    rows = (
        db.query(SharedSelectorPerformance)
        .filter(SharedSelectorPerformance.field_fp.in_(payload.fps))
        .filter_by(ats_platform=ats)
        .filter(SharedSelectorPerformance.success_count >= 3)
        .order_by(SharedSelectorPerformance.success_count.desc())
        .all()
    )
    result: dict[str, list] = {}
    for row in rows:
        rate = (row.success_count or 0) / max((row.success_count or 0) + (row.fail_count or 0), 1)
        result.setdefault(row.field_fp, []).append({
            "selector": row.selector,
            "type": row.selector_type,
            "rate": round(rate, 3),
        })
    return {"selectors": result}


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
async def save_job(
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

    from backend.app.utils import cache
    await cache.delete(f"dashboard_summary:{current_user.id}")

    logger.info("Job saved user_id=%s job_id=%s company=%s", current_user.id, job.id, job.company)
    return {"id": job.id, "message": "Job saved successfully"}


# Statuses that count as "applied" for dashboard (past saved stage)
APPLIED_STATUSES = frozenset({"applied", "interview", "closed"})


def _parse_date(d: str | None):
    """Parse YYYY-MM-DD string to datetime at midnight UTC."""
    if not d:
        return None
    try:
        return datetime.strptime(d.strip()[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


@router.get("/jobs")
def list_user_jobs(
    status: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List user's saved jobs. Optional ?status=applied, ?from_date=YYYY-MM-DD, ?to_date=YYYY-MM-DD."""
    q = db.query(UserJob).filter(UserJob.user_id == current_user.id)
    start_dt = _parse_date(from_date)
    end_dt = _parse_date(to_date)
    if end_dt:
        end_dt = datetime(end_dt.year, end_dt.month, end_dt.day, 23, 59, 59)
    if start_dt:
        q = q.filter(UserJob.created_at >= start_dt)
    if end_dt:
        q = q.filter(UserJob.created_at <= end_dt)
    q = q.order_by(UserJob.created_at.desc())
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
class CoverLetterUpsertIn(BaseModel):
    job_url: str = ""
    page_html: str = ""
    job_title: str | None = None


@router.post("/cover-letter/upsert")
def cover_letter_upsert(
    payload: CoverLetterUpsertIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Upsert cover letter: if existing one matches job_url, return it.
    Else generate via LLM, store, return. Same shape as old /generate.
    """
    from backend.app.services.cover_letter_service import generate_cover_letter as gen_cover

    profile = ProfileService.get_or_create_profile(db, current_user)
    prefs = dict(profile.preferences or {})
    cl = prefs.get("cover_letter") or {}
    if isinstance(cl, dict):
        stored_url = (cl.get("job_url") or "").strip()
        incoming_url = (payload.job_url or "").strip()
        if stored_url and incoming_url and stored_url == incoming_url:
            return {
                "content": cl.get("content") or "",
                "job_title": cl.get("job_title") or "",
            }

    job_title = (payload.job_title or "").strip()
    job_description = ""
    if payload.page_html and len(payload.page_html.strip()) > 100:
        job_description = parse_job_description_from_html(payload.page_html) or ""
    job_description = (job_description or "").strip()

    pl = profile_model_to_payload(profile)
    content = gen_cover(pl, job_title=job_title, job_description=job_description)

    prefs["cover_letter"] = {
        "content": content or "",
        "job_title": job_title,
        "job_description": job_description[:500],
        "job_url": (payload.job_url or "").strip(),
        "updated_at": None,
    }
    profile.preferences = prefs
    db.commit()
    return {"content": content or "", "job_title": job_title}


# --- Extension Error Reporting ---
@router.post("/errors")
async def report_extension_error(payload: dict[str, Any]) -> dict:
    """
    Accept extension error reports for monitoring.
    Auth optional - extensions may report when user is logged out.
    """
    logger.warning(
        "Extension error report: type=%s msg=%s url=%s env=%s",
        payload.get("type", "unknown"),
        (payload.get("message") or "")[:200],
        (payload.get("url") or "")[:100],
        payload.get("environment"),
    )
    return {"ok": True}
