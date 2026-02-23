"""
Resume service - single source of truth for resume list and storage operations.
Used by GET /api/resume, chrome-extension, and autofill.
"""
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.models.user_resume import UserResume
from backend.app.schemas.profile import profile_model_to_payload
from backend.app.services.profile_service import ProfileService, build_resume_text_from_payload
from backend.app.services.s3_service import delete_file_from_s3, parse_s3_key_from_url

logger = get_logger("services.resume")


def list_resumes(db: Session, user: User) -> list[dict]:
    """
    List user's resumes. Single source - UserResume first, profile fallback when empty.
    Returns list of {id, resume_name, resume_url, resume_text, is_default}.
    """
    items = []
    for r in (
        db.query(UserResume)
        .filter(UserResume.user_id == user.id)
        .order_by(UserResume.is_default.desc(), UserResume.created_at.desc())
        .all()
    ):
        items.append({
            "id": r.id,
            "resume_name": r.resume_name,
            "resume_url": r.resume_url,
            "resume_text": r.resume_text or "",
            "is_default": bool(r.is_default),
        })
    if not items:
        profile = ProfileService.get_or_create_profile(db, user)
        if profile.resume_url:
            prefs = profile.preferences or {}
            custom_name = (prefs.get("resume_display_name") or "").strip()
            base_name = Path(profile.resume_url).name.split("?")[0] or "Resume"
            name = f"{(custom_name or base_name)} (default)"
            text_override = (prefs.get("resume_text_override") or "").strip()
            pl = profile_model_to_payload(profile)
            resume_text = text_override if text_override else (build_resume_text_from_payload(pl) or "")
            items.append({
                "id": 0,
                "resume_name": name,
                "resume_url": profile.resume_url,
                "resume_text": resume_text,
                "is_default": True,
            })
    return items


def delete_file_from_storage(resume_url: str | None, user_id: int) -> bool:
    """Delete resume file from S3 or local storage. Returns True if deleted or not found."""
    if not resume_url:
        return True
    # S3
    key = parse_s3_key_from_url(resume_url)
    if key:
        return delete_file_from_s3(key)
    # Local: /uploads/resumes/filename.pdf
    if resume_url.startswith("/") and settings.upload_dir in resume_url:
        safe_name = Path(resume_url).name.split("?")[0]
        if safe_name:
            upload_path = Path(settings.upload_dir) / safe_name
            if upload_path.exists():
                try:
                    upload_path.unlink()
                    logger.info("Deleted local resume file user_id=%s path=%s", user_id, upload_path)
                    return True
                except OSError as e:
                    logger.warning("Failed to delete local resume %s: %s", upload_path, e)
                    return False
        return True
    return True
