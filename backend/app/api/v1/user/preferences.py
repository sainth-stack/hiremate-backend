"""
User resume preferences endpoints - template, fonts, colors, editor settings.
"""
from datetime import datetime

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.user import User
from backend.app.models.user_resume_preference import UserResumePreference

router = APIRouter()

_DEFAULTS = {
    "default_template_id": "classic-pro",
    "default_font_family": "Inter",
    "default_color_scheme": "default",
    "preferred_paper_size": "A4",
    "default_tone": "professional",
    "show_keyword_score": True,
    "auto_save_ms": 300,
    "preferred_sections": [],
}


class UserPreferencesUpdateIn(BaseModel):
    default_template_id: str | None = None
    default_font_family: str | None = None
    default_color_scheme: str | None = None
    preferred_paper_size: str | None = None
    default_tone: str | None = None
    show_keyword_score: bool | None = None
    auto_save_ms: int | None = None
    preferred_sections: list | None = None


@router.get("/preferences")
def get_user_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Load user resume preferences. Returns defaults when none have been saved."""
    prefs = db.query(UserResumePreference).filter(
        UserResumePreference.user_id == current_user.id
    ).first()
    if not prefs:
        return _DEFAULTS
    return {
        "default_template_id": prefs.default_template_id,
        "default_font_family": prefs.default_font_family,
        "default_color_scheme": prefs.default_color_scheme,
        "preferred_paper_size": prefs.preferred_paper_size,
        "default_tone": prefs.default_tone,
        "show_keyword_score": prefs.show_keyword_score,
        "auto_save_ms": prefs.auto_save_ms,
        "preferred_sections": prefs.preferred_sections or [],
    }


@router.patch("/preferences")
def update_user_preferences(
    payload: UserPreferencesUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save user resume preferences (upsert)."""
    prefs = db.query(UserResumePreference).filter(
        UserResumePreference.user_id == current_user.id
    ).first()
    if not prefs:
        prefs = UserResumePreference(
            user_id=current_user.id,
            **{k: v for k, v in _DEFAULTS.items() if k != "preferred_sections"},
            preferred_sections=[],
        )
        db.add(prefs)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, key, value)

    prefs.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(prefs)
    return {
        "default_template_id": prefs.default_template_id,
        "default_font_family": prefs.default_font_family,
        "default_color_scheme": prefs.default_color_scheme,
        "preferred_paper_size": prefs.preferred_paper_size,
        "default_tone": prefs.default_tone,
        "show_keyword_score": prefs.show_keyword_score,
        "auto_save_ms": prefs.auto_save_ms,
        "preferred_sections": prefs.preferred_sections or [],
    }
