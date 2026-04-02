from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.jobradar.models.nudge import Nudge
from backend.app.models.user import User

router = APIRouter()


@router.get("")
def list_nudges(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all nudges for the current user, newest first."""
    nudges = (
        db.query(Nudge)
        .filter(Nudge.user_id == current_user.id)
        .order_by(Nudge.created_at.desc())
        .all()
    )
    return [
        {
            "id": n.id,
            "application_id": n.application_id,
            "message": n.message,
            "nudge_type": n.nudge_type,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in nudges
    ]


@router.patch("/{nudge_id}/read")
def mark_read(
    nudge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a nudge as read."""
    nudge = (
        db.query(Nudge)
        .filter(Nudge.id == nudge_id, Nudge.user_id == current_user.id)
        .first()
    )
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")
    nudge.is_read = True
    db.commit()
    return {"success": True}


@router.patch("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all nudges as read for the current user."""
    db.query(Nudge).filter(
        Nudge.user_id == current_user.id,
        Nudge.is_read == False,  # noqa: E712
    ).update({"is_read": True})
    db.commit()
    return {"success": True}
