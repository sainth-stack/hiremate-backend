"""
Resume service - single source of truth for resume list and storage operations.
Used by GET /api/resume/workspace, chrome-extension, and autofill.
"""
from datetime import datetime
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

# Resume studio table badge (synthetic profile row uses RESUME_SOURCE_DEFAULT in API only).
RESUME_SOURCE_DEFAULT = "default"
RESUME_SOURCE_UPLOADED = "uploaded"
RESUME_SOURCE_GENERATED = "generated"
RESUME_SOURCE_UPDATED = "updated"


def touch_resume_edit(r: UserResume) -> None:
    """Mark a UserResume as user-edited (last_edited + badge: uploaded/generated → updated)."""
    r.updated_at = datetime.utcnow()
    if r.resume_source in (RESUME_SOURCE_UPLOADED, RESUME_SOURCE_GENERATED):
        r.resume_source = RESUME_SOURCE_UPDATED


def _effective_updated_at(r: UserResume) -> datetime | None:
    return r.updated_at or r.created_at


def _dt_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.isoformat()


def resume_timestamps_for_api(r: UserResume) -> dict[str, str | None]:
    """created_at, updated_at (last edited = updated or created), resume_source for list/detail APIs."""
    eff = _effective_updated_at(r)
    return {
        "created_at": _dt_iso(r.created_at),
        "updated_at": _dt_iso(eff),
        "resume_source": r.resume_source,
    }


def list_resumes(db: Session, user: User) -> list[dict]:
    """
    List user's resumes. Single source - UserResume first, profile fallback when empty.
    Returns list of {id, resume_name, resume_url, resume_text, is_default,
                     resume_profile_snapshot, job_title, job_description_snippet,
                     created_at, updated_at, resume_source}.
    """
    items = []
    for r in (
        db.query(UserResume)
        .filter(UserResume.user_id == user.id)
        .order_by(UserResume.is_default.desc(), UserResume.created_at.desc())
        .all()
    ):
        row = {
            "id": r.id,
            "resume_name": r.resume_name,
            "resume_url": r.resume_url,
            "resume_text": r.resume_text or "",
            "is_default": bool(r.is_default),
            "resume_profile_snapshot": r.resume_profile_snapshot or None,
            "job_title": r.job_title or "",
            "job_description_snippet": r.job_description_snippet or "",
        }
        row.update(resume_timestamps_for_api(r))
        items.append(row)
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
            created = profile.created_at
            last_edited = profile.updated_at or created
            items.append({
                "id": 0,
                "resume_name": name,
                "resume_url": profile.resume_url,
                "resume_text": resume_text,
                "is_default": True,
                "resume_profile_snapshot": None,
                "job_title": "",
                "job_description_snippet": "",
                "created_at": _dt_iso(created),
                "updated_at": _dt_iso(last_edited),
                "resume_source": RESUME_SOURCE_DEFAULT,
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
