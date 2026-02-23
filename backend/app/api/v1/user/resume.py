"""
Resume upload and generation endpoints - uploads to S3, generates JD-optimized resumes via Jinja2+WeasyPrint
"""
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

from pydantic import BaseModel

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user, get_db
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.models.user_resume import UserResume
from backend.app.schemas.profile import ProfilePayload, profile_model_to_payload
from backend.app.services.pdf_generator import text_to_pdf_bytes
from backend.app.services.profile_service import ProfileService, build_resume_text_from_payload
from backend.app.services.resume_extractor import extract_resume_to_payload
from backend.app.services.resume_generator import generate_resume_html
from backend.app.services.resume_service import delete_file_from_storage, list_resumes as list_resumes_svc
from backend.app.services.s3_service import upload_file_to_s3
from backend.app.services.tailor_context_store import get_and_clear_tailor_context

logger = get_logger("api.user.resume")
router = APIRouter()


class ResumeUpdateIn(BaseModel):
    resume_name: str | None = None
    resume_text: str | None = None


class GenerateResumeIn(BaseModel):
    job_title: str = ""
    job_description: str = ""


@router.get("/tailor-context")
def get_tailor_context(
    current_user: User = Depends(get_current_user),
):
    """
    Fetch and clear stored tailor context from extension (JD + title).
    Used when opening resume-generator via "Tailor Resume" on a job page.
    """
    ctx = get_and_clear_tailor_context(current_user.id)
    if not ctx:
        return {}
    return ctx


@router.post("/generate")
def generate_resume(
    payload: GenerateResumeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a JD-optimized resume from user profile.
    Uses Jinja2 HTML template + WeasyPrint. Same user profile, bullets prioritized by JD keywords.
    Returns resume_id, resume_url, presigned_url, resume_name, resume_text (for edit popup).
    """
    try:
        result = generate_resume_html(
            db=db,
            user=current_user,
            job_title=(payload.job_title or "").strip(),
            job_description=(payload.job_description or "").strip(),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception("Resume generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{resume_id}/file")
def get_resume_file(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Proxy resume PDF through backend to avoid S3 CORS. Returns the PDF file."""
    if resume_id == 0:
        profile = ProfileService.get_or_create_profile(db, current_user)
        resume_url = profile.resume_url
        if not resume_url:
            raise HTTPException(status_code=404, detail="No resume found")
    else:
        r = db.query(UserResume).filter(UserResume.id == resume_id, UserResume.user_id == current_user.id).first()
        if not r or not r.resume_url:
            raise HTTPException(status_code=404, detail="Resume not found")
        resume_url = r.resume_url

    filename = Path(resume_url).name.split("?")[0] or "resume.pdf"

    if resume_url.startswith("http://") or resume_url.startswith("https://"):
        try:
            with urlopen(resume_url, timeout=30) as resp:
                data = resp.read()
            logger.info("Proxied resume from S3 user_id=%s resume_id=%s bytes=%d", current_user.id, resume_id, len(data))
            return Response(
                content=data,
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{filename}"'},
            )
        except Exception as exc:
            logger.exception("Failed to proxy resume from %s", resume_url)
            raise HTTPException(status_code=502, detail=f"Failed to fetch resume: {str(exc)}") from exc

    upload_base = Path(settings.upload_dir)
    if not upload_base.is_absolute():
        upload_base = Path.cwd() / upload_base
    resume_path = upload_base / filename
    if not resume_path.exists():
        raise HTTPException(status_code=404, detail="Resume file not found")
    return FileResponse(resume_path, media_type="application/pdf", filename=filename)


@router.get("")
def list_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's resumes. Single source - used by frontend and extension."""
    return list_resumes_svc(db, current_user)


@router.patch("/{resume_id}")
def update_resume(
    resume_id: int,
    payload: ResumeUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update resume name and/or content. Regenerates PDF when content changes."""
    if resume_id == 0:
        profile = ProfileService.get_or_create_profile(db, current_user)
        if not profile.resume_url:
            raise HTTPException(status_code=404, detail="No profile resume to edit")
        prefs = dict(profile.preferences or {})
        name_val = (payload.resume_name or "").strip()
        if name_val:
            prefs["resume_display_name"] = (name_val.replace(" (default)", "").strip() or name_val)[:200]
        if payload.resume_text is not None:
            prefs["resume_text_override"] = payload.resume_text or ""
        profile.preferences = prefs
        db.commit()
        db.refresh(profile)
        display = prefs.get("resume_display_name") or Path(profile.resume_url).name.split("?")[0] or "Resume"
        text_override = prefs.get("resume_text_override")
        if payload.resume_text is not None and text_override:
            _regenerate_pdf_for_profile(db, profile, current_user, text_override, display)
        return {"id": 0, "resume_name": f"{display} (default)", "resume_text": text_override}
    if resume_id < 0:
        raise HTTPException(status_code=400, detail="Invalid resume id")
    r = db.query(UserResume).filter(UserResume.id == resume_id, UserResume.user_id == current_user.id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Resume not found")
    if payload.resume_name is not None:
        name = (payload.resume_name or "").strip()
        if name:
            r.resume_name = name
    text_updated = False
    if payload.resume_text is not None:
        r.resume_text = payload.resume_text or ""
        text_updated = True
    db.commit()
    if text_updated and r.resume_text:
        _regenerate_pdf_for_user_resume(db, r, current_user)
    db.refresh(r)
    return {"id": r.id, "resume_name": r.resume_name, "resume_text": r.resume_text}


def _regenerate_pdf_for_user_resume(db: Session, r: UserResume, user: User) -> None:
    """Regenerate PDF from resume_text and replace the stored file."""
    try:
        pdf_bytes = text_to_pdf_bytes(r.resume_text, r.resume_name.replace(" (default)", ""))
        filename = (r.resume_url or "").split("/")[-1].split("?")[0] or f"{uuid.uuid4()}.pdf"
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            result = upload_file_to_s3(pdf_bytes, filename, user.id, "application/pdf", "user-profiles")
            r.resume_url = result["url"]
        else:
            upload_path = Path(settings.upload_dir)
            upload_path.mkdir(parents=True, exist_ok=True)
            file_path = upload_path / filename
            file_path.write_bytes(pdf_bytes)
            r.resume_url = f"/{settings.upload_dir}/{filename}"
        db.commit()
        logger.info("Regenerated PDF for UserResume id=%s", r.id)
    except Exception as e:
        logger.warning("PDF regeneration failed for resume id=%s: %s", r.id, e)


def _regenerate_pdf_for_profile(db: Session, profile, user: User, text: str, display_name: str) -> None:
    """Regenerate PDF for profile fallback and update resume_url."""
    try:
        pdf_bytes = text_to_pdf_bytes(text, display_name)
        filename = (profile.resume_url or "").split("/")[-1].split("?")[0] or f"{uuid.uuid4()}.pdf"
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            result = upload_file_to_s3(pdf_bytes, filename, user.id, "application/pdf", "user-profiles")
            profile.resume_url = result["url"]
        else:
            upload_path = Path(settings.upload_dir)
            upload_path.mkdir(parents=True, exist_ok=True)
            file_path = upload_path / filename
            file_path.write_bytes(pdf_bytes)
            profile.resume_url = f"/{settings.upload_dir}/{filename}"
        db.commit()
        logger.info("Regenerated PDF for profile user_id=%s", user.id)
    except Exception as e:
        logger.warning("PDF regeneration failed for profile: %s", e)


@router.delete("/{resume_id}")
def delete_resume_by_id(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a UserResume by id. Removes file from S3/local, then DB record."""
    if resume_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Use DELETE /resume to remove profile resume",
        )
    r = db.query(UserResume).filter(UserResume.id == resume_id, UserResume.user_id == current_user.id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Resume not found")
    delete_file_from_storage(r.resume_url, current_user.id)
    db.delete(r)
    db.commit()
    return {"deleted": resume_id}


ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a resume file (PDF, DOC, DOCX).

    Stores in S3 under user-profiles/{user_id}/{filename}. Each user can have multiple resumes.
    Extracts profile data from PDF via LLM and updates the user's profile.

    Returns:
        - **resumeUrl**: S3 URL to the uploaded file (for UI display/download)
        - **resumeLastUpdated**: ISO 8601 timestamp
        - **profile**: Full profile data as stored in DB
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        logger.warning(
            "Resume upload rejected - invalid file type user_id=%s filename=%s",
            current_user.id,
            file.filename,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    logger.info(
        "Resume upload started user_id=%s filename=%s",
        current_user.id,
        file.filename,
    )

    unique_name = f"{uuid.uuid4()}{suffix}"
    mime_type = MIME_TYPES.get(suffix, "application/octet-stream")

    try:
        contents = await file.read()
    except Exception as e:
        logger.exception(
            "Resume upload failed - could not read file user_id=%s error=%s",
            current_user.id,
            str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

    # Upload to S3: user-profiles/{user_id}/{filename}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        try:
            result = upload_file_to_s3(
                file_buffer=contents,
                file_name=unique_name,
                user_id=current_user.id,
                mime_type=mime_type,
                key_prefix="user-profiles",
            )
            resume_url = result["url"]
        except Exception as e:
            logger.exception(
                "Resume upload failed - S3 upload error user_id=%s error=%s",
                current_user.id,
                str(e),
            )
            raise HTTPException(status_code=500, detail=f"Failed to upload to S3: {str(e)}")
    else:
        # Fallback: local storage when AWS not configured
        upload_path = Path(settings.upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)
        file_path = upload_path / unique_name
        file_path.write_bytes(contents)
        resume_url = f"/{settings.upload_dir}/{unique_name}"

    resume_last_updated = datetime.utcnow().isoformat() + "Z"

    # Extract data from PDF using LLM (requires temp file for extraction)
    if suffix == ".pdf":
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        try:
            payload = extract_resume_to_payload(
                tmp_path,
                resume_url=resume_url,
                resume_last_updated=resume_last_updated,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    else:
        payload = ProfilePayload(
            resumeUrl=resume_url,
            resumeLastUpdated=resume_last_updated,
        )

    # Save extracted profile to database
    try:
        profile = ProfileService.update_profile(db, current_user, payload)
        payload = profile_model_to_payload(profile)
    except Exception as e:
        logger.exception(
            "Resume upload failed - profile save error user_id=%s error=%s",
            current_user.id,
            str(e),
        )
        raise HTTPException(status_code=500, detail=f"Profile save error: {str(e)}")

    # Add to user_resumes for keyword analyser dropdown
    try:
        resume_name = Path(file.filename or unique_name).stem
        if not resume_name:
            resume_name = "Resume"
        resume_text = build_resume_text_from_payload(payload)
        for r in db.query(UserResume).filter(UserResume.user_id == current_user.id).all():
            r.is_default = 0
        ur = UserResume(
            user_id=current_user.id,
            resume_url=resume_url,
            resume_name=f"{resume_name} (default)",
            resume_text=resume_text,
            is_default=1,
        )
        db.add(ur)
        db.commit()
    except Exception as e:
        logger.warning("Failed to add resume to user_resumes: %s", e)
        db.rollback()

    logger.info(
        "Resume uploaded and profile created/updated successfully user_id=%s filename=%s",
        current_user.id,
        unique_name,
    )
    return payload.model_dump()


@router.delete("", response_model=ProfilePayload)
def delete_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete the current user's resume from their profile.
    Removes file from S3/local, then clears profile.resume_url.
    """
    logger.info("Resume delete requested user_id=%s", current_user.id)
    try:
        profile = ProfileService.get_or_create_profile(db, current_user)
        had_resume = bool(profile.resume_url)
        if had_resume:
            delete_file_from_storage(profile.resume_url, current_user.id)
        profile.resume_url = None
        profile.resume_last_updated = None
        db.commit()
        db.refresh(profile)
        if had_resume:
            logger.info(
                "Resume deleted successfully user_id=%s",
                current_user.id,
            )
        else:
            logger.info(
                "Resume delete - no resume was present user_id=%s",
                current_user.id,
            )
        return profile_model_to_payload(profile)
    except Exception as e:
        logger.exception(
            "Resume delete failed user_id=%s error=%s",
            current_user.id,
            str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to delete resume: {str(e)}")
