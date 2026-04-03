from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.jobradar.models.application import Application
from backend.app.models.user import User

router = APIRouter()

ACTIVE_STATUSES = {"applied", "acknowledged", "in_review", "interview_scheduled", "interview_completed"}


@router.get("")
def get_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return aggregated job application metrics for the current user."""
    apps = (
        db.query(
            Application.platform,
            Application.current_status,
        )
        .filter(Application.user_id == current_user.id)
        .all()
    )

    total = len(apps)
    by_status: dict[str, int] = {}
    by_platform: dict[str, int] = {}

    for app in apps:
        s = app.current_status or "unknown"
        p = app.platform or "Unknown"
        by_status[s] = by_status.get(s, 0) + 1
        by_platform[p] = by_platform.get(p, 0) + 1

    in_progress = sum(v for k, v in by_status.items() if k in ACTIVE_STATUSES)
    offers = by_status.get("offer_received", 0)
    interviews = by_status.get("interview_scheduled", 0) + by_status.get("interview_completed", 0)
    response_rate = (
        round((total - by_status.get("applied", 0)) / total * 100, 1) if total else 0
    )

    return {
        "total": total,
        "in_progress": in_progress,
        "offers": offers,
        "interviews": interviews,
        "response_rate": response_rate,
        "by_status": by_status,
        "by_platform": by_platform,
    }
