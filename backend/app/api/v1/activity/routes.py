"""
Activity tracking API - career page views, autofill usage.
"""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.models.career_page_visit import CareerPageVisit

logger = get_logger("api.activity")
router = APIRouter(prefix="/activity", tags=["activity"])


class ActivityTrackIn(BaseModel):
    event_type: Literal["career_page_view", "autofill_used"]
    page_url: str
    metadata: dict = {}


@router.post("/track")
def track_activity(
    payload: ActivityTrackIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Track career page view or autofill usage. Same DB logic as deleted routes."""
    meta = payload.metadata or {}
    company_name = meta.get("company_name")
    job_url = meta.get("job_url")
    job_title = meta.get("job_title")

    if payload.event_type == "career_page_view":
        action_type = "page_view"
    else:
        action_type = "autofill_used"

    visit = CareerPageVisit(
        user_id=current_user.id,
        page_url=payload.page_url,
        company_name=company_name,
        job_url=job_url,
        job_title=job_title,
        action_type=action_type,
    )
    db.add(visit)
    db.commit()

    logger.info(
        "Activity tracked user_id=%s event=%s page_url=%s",
        current_user.id,
        payload.event_type,
        payload.page_url[:80],
    )
    return {"ok": True}
