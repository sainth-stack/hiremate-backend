from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.core.dependencies import get_db, get_current_user, require_ai_token_balance
from backend.app.models.user import User
from backend.jobradar.models.application import Application
from backend.jobradar.services.briefing_service import BriefingService

router = APIRouter()


@router.get("/briefing", dependencies=[Depends(require_ai_token_balance)])
def get_company_briefing(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches an AI-powered briefing for the given application's company/role.
    """
    # 1. Fetch Application
    app = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id
    ).first()

    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # 2. Get Briefing
    service = BriefingService(db)
    briefing = service.get_or_generate_briefing(app.company, app.role, current_user.id, current_user.email)
    
    if not briefing:
        raise HTTPException(status_code=500, detail="Failed to generate briefing")

    return briefing.dict()
