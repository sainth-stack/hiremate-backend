"""
Resume upload endpoints - uploads to S3 (user-profiles/{user_id}/), extracts data, stores in DB
"""
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user, get_db
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.models.user_resume import UserResume
from backend.app.schemas.profile import ProfilePayload, profile_model_to_payload
from backend.app.services.profile_service import ProfileService, build_resume_text_from_payload
from backend.app.services.resume_extractor import extract_resume_to_payload
from backend.app.services.s3_service import upload_file_to_s3

logger = get_logger("api.user.resume")
router = APIRouter()

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
    Clears resume URL and last updated timestamp.
    """
    logger.info("Resume delete requested user_id=%s", current_user.id)
    try:
        profile = ProfileService.get_or_create_profile(db, current_user)
        had_resume = bool(profile.resume_url)
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
