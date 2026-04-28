"""
Legal API routes.

Public:
  GET  /api/legal/privacy-policy          — fetch current privacy policy
  GET  /api/legal/privacy-policy/history  — version history list
  GET  /api/legal/terms-of-service        — fetch current terms of service
  GET  /api/legal/terms-of-service/history — version history list

Admin-only:
  PUT  /api/legal/privacy-policy          — publish a new version
  PUT  /api/legal/terms-of-service        — publish a new version
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


@router.get("/terms-of-service", response_model=LegalPolicyResponse)
def get_terms_of_service(db: Session = Depends(get_db)):
    """Return the current (is_current=True) terms of service. Public endpoint."""
    policy = LegalService.get_current_policy(db, "terms_of_service")
    if not policy:
        raise HTTPException(status_code=404, detail="Terms of service not found")
    return policy


@router.get("/terms-of-service/history", response_model=list[LegalPolicyHistoryItem])
def get_terms_of_service_history(db: Session = Depends(get_db)):
    """Return version history (newest first). Public endpoint."""
    return LegalService.get_policy_history(db, "terms_of_service")


@router.put("/terms-of-service", response_model=LegalPolicyResponse)
def update_terms_of_service(
    body: LegalPolicyUpsertRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Publish a new version of the terms of service. Admin only."""
    policy = LegalService.upsert_policy(
        db,
        policy_type="terms_of_service",
        version=body.version,
        title=body.title,
        content=body.content,
    )
    return policy
