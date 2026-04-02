from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from backend.app.core.dependencies import get_current_user, get_db
from backend.jobradar.models.application import Application, StatusHistory
from backend.app.models.user import User

router = APIRouter()


@router.get("")
def list_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all Gmail-synced applications for the current user, most recent activity first."""
    apps = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.last_activity.desc())
        .all()
    )
    return [_serialize(a) for a in apps]


@router.get("/{app_id}")
def get_application(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single application with its full status history."""
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    history = (
        db.query(StatusHistory)
        .filter(StatusHistory.application_id == app_id)
        .order_by(StatusHistory.changed_at.asc())
        .all()
    )

    data = _serialize(app)
    data["history"] = [
        {
            "id": h.id,
            "status": h.status,
            "changed_at": h.changed_at.isoformat() if h.changed_at else None,
            "raw_email_id": h.raw_email_id,
            "summary": h.summary,
        }
        for h in history
    ]
    return data


@router.post("")
def create_application(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually add a new application to the tracker."""
    new_app = Application(
        user_id=current_user.id,
        company=payload.get("company"),
        role=payload.get("role") or payload.get("position_title"),
        platform=payload.get("platform") or "Manual",
        current_status=payload.get("current_status") or "applied",
        applied_date=datetime.utcnow(),
        job_url=payload.get("job_url") or payload.get("job_posting_url"),
    )
    db.add(new_app)
    db.flush()
    
    db.add(StatusHistory(
        application_id=new_app.id,
        status=new_app.current_status,
        summary="Application manually added by user",
    ))
    db.commit()
    db.refresh(new_app)
    return _serialize(new_app)


@router.patch("/{app_id}")
def update_application(
    app_id: int,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing application's details or status."""
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if "company" in payload: app.company = payload["company"]
    if "role" in payload: app.role = payload["role"]
    if "position_title" in payload: app.role = payload["position_title"]
    if "job_url" in payload: app.job_url = payload["job_url"]
    if "job_posting_url" in payload: app.job_url = payload["job_posting_url"]
    
    if "current_status" in payload and payload["current_status"] != app.current_status:
        app.current_status = payload["current_status"]
        app.last_activity = datetime.utcnow()
        db.add(StatusHistory(
            application_id=app.id,
            status=app.current_status,
            summary=payload.get("status_summary") or "Status manually updated",
        ))

    db.commit()
    return _serialize(app)


@router.delete("/{app_id}")
def delete_application(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an application record."""
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    db.delete(app)
    db.commit()
    return {"success": True}


@router.patch("/{app_id}/withdraw")
def withdraw_application(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an application as withdrawn."""
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.current_status = "withdrawn"
    db.add(StatusHistory(
        application_id=app.id,
        status="withdrawn",
        summary="User marked application as withdrawn",
    ))
    db.commit()
    return {"success": True}


def _serialize(app: Application) -> dict:
    return {
        "id": app.id,
        "company": app.company,
        "role": app.role,
        "platform": app.platform,
        "current_status": app.current_status,
        "applied_date": app.applied_date.isoformat() if app.applied_date else None,
        "last_activity": app.last_activity.isoformat() if app.last_activity else None,
        "next_action": app.next_action,
        "job_url": app.job_url,
        "confidence": app.confidence,
        "low_confidence": app.low_confidence,
        "email_thread_id": app.email_thread_id,
        "interview_process": app.interview_process,
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }
