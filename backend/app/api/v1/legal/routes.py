"""
Legal API routes.

Public:
  GET  /api/legal/privacy-policy          — fetch current privacy policy
  GET  /api/legal/privacy-policy/history  — version history list

Admin-only:
  PUT  /api/legal/privacy-policy          — publish a new version
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_admin_user, get_db
from backend.app.models.user import User
from backend.app.schemas.legal import (
    LegalPolicyHistoryItem,
    LegalPolicyResponse,
    LegalPolicyUpsertRequest,
)
from backend.app.services.legal_service import LegalService

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/privacy-policy", response_model=LegalPolicyResponse)
def get_privacy_policy(db: Session = Depends(get_db)):
    """Return the current (is_current=True) privacy policy. Public endpoint."""
    policy = LegalService.get_current_policy(db, "privacy_policy")
    if not policy:
        raise HTTPException(status_code=404, detail="Privacy policy not found")
    return policy


@router.get("/privacy-policy/history", response_model=list[LegalPolicyHistoryItem])
def get_privacy_policy_history(db: Session = Depends(get_db)):
    """Return version history (newest first). Public endpoint."""
    return LegalService.get_policy_history(db, "privacy_policy")


@router.put("/privacy-policy", response_model=LegalPolicyResponse)
def update_privacy_policy(
    body: LegalPolicyUpsertRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Publish a new version of the privacy policy. Admin only."""
    policy = LegalService.upsert_policy(
        db,
        policy_type="privacy_policy",
        version=body.version,
        title=body.title,
        content=body.content,
    )
    return policy
