"""
Profile endpoints - GET and PATCH profile data (PROFILE_PAYLOAD_SCHEMA format)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.user import User
from backend.app.schemas.profile import ProfilePayload, profile_model_to_payload
from backend.app.services.profile_service import ProfileService
from backend.app.utils import cache

router = APIRouter()


@router.get("", response_model=ProfilePayload)
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's profile. Returns empty schema if none exists."""
    profile = ProfileService.get_or_create_profile(db, current_user)
    return profile_model_to_payload(profile)


@router.patch("", response_model=ProfilePayload)
async def update_profile(
    payload: ProfilePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user's profile with full PROFILE_PAYLOAD_SCHEMA data."""
    profile = ProfileService.update_profile(db, current_user, payload)
    result = profile_model_to_payload(profile)
    user_id = current_user.id
    await cache.delete(f"dashboard_summary:{user_id}")
    await cache.delete(f"autofill_ctx:{user_id}")
    return result
