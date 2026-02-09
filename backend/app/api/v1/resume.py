"""
Resume upload endpoints - saves file, extracts data with pdfplumber, stores in DB
"""
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.user import User
from backend.app.schemas.profile import profile_model_to_payload
from backend.app.services.profile_service import ProfileService
from backend.app.services.resume_extractor import extract_resume_to_payload
from sqlalchemy.orm import Session

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a resume file (PDF, DOC, DOCX).

    Requires authentication. Saves the file and creates/updates the user's profile
    with resumeUrl and resumeLastUpdated in the database (PROFILE_PAYLOAD_SCHEMA format).

    Returns:
        - **resumeUrl**: URL/path to the uploaded file
        - **resumeLastUpdated**: ISO 8601 timestamp
        - **profile**: Full profile data as stored in DB
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4()}{suffix}"
    file_path = upload_path / unique_name

    try:
        contents = await file.read()
        file_path.write_bytes(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    resume_url = f"/{settings.upload_dir}/{unique_name}"
    resume_last_updated = datetime.utcnow().isoformat() + "Z"

    # Extract data from PDF using pdfplumber (only for PDF)
    if suffix == ".pdf":
        payload = extract_resume_to_payload(
            file_path,
            resume_url=resume_url,
            resume_last_updated=resume_last_updated,
        )
    else:
        from backend.app.schemas.profile import ProfilePayload
        payload = ProfilePayload(
            resumeUrl=resume_url,
            resumeLastUpdated=resume_last_updated,
        )

    # Save extracted profile to database
    try:
        profile = ProfileService.update_profile(db, current_user, payload)
        payload = profile_model_to_payload(profile)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Profile save error: {str(e)}")

    return payload.model_dump()
