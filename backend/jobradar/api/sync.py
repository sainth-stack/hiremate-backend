from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.jobradar.models.application import SyncStatus
from backend.app.models.user import User
from backend.jobradar.tasks.sync_task import sync_user_emails

router = APIRouter()


@router.post("")
def trigger_sync(
    background_tasks: BackgroundTasks,
    from_date: str = None,
    to_date: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a Gmail sync with optional date range (YYYY-MM-DD)."""
    # Check if already running
    sync = db.query(SyncStatus).filter(SyncStatus.user_id == current_user.id).first()
    if sync and sync.status == "running":
        return {"status": "error", "message": "Sync already in progress"}

    # Upsert sync_status row as running
    if sync:
        sync.status = "running"
        sync.total_threads = 0
        sync.parsed_count = 0
        sync.ai_count = 0
        sync.ai_success_count = 0
        sync.last_updated = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        sync = SyncStatus(
            user_id=current_user.id,
            status="running",
            total_threads=0,
            parsed_count=0,
            ai_count=0,
            ai_success_count=0,
            last_updated=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(sync)
    db.commit()

    background_tasks.add_task(sync_user_emails, current_user.id, from_date, to_date)
    return {"status": "queued"}


@router.get("/status")
def get_sync_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current sync progress for the user."""
    sync = db.query(SyncStatus).filter(SyncStatus.user_id == current_user.id).first()
    if not sync:
        return {"status": "idle", "total_threads": 0, "parsed_count": 0, "ai_count": 0, "ai_success_count": 0}
    return {
        "status": sync.status,
        "total_threads": sync.total_threads,
        "parsed_count": sync.parsed_count,
        "ai_count": sync.ai_count,
        "ai_success_count": sync.ai_success_count,
        "last_updated": sync.last_updated.isoformat() if sync.last_updated else None,
    }


@router.post("/stop")
def stop_sync(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Signal the running sync task to stop."""
    sync = db.query(SyncStatus).filter(SyncStatus.user_id == current_user.id).first()
    if sync and sync.status == "running":
        sync.status = "stopped"
        sync.last_updated = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    return {"status": "stopping"}
