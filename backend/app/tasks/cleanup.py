"""
Periodic cleanup: remove stale one-off user_field_answers entries.
Run via cron or: python -c "from backend.app.tasks.cleanup import run_cleanup; print(run_cleanup())"
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.form_field_learning import UserFieldAnswer


def cleanup_stale_field_answers(db: Session) -> dict:
    """
    Delete user_field_answers where used_count=1 and last_used > 90 days ago.
    These are one-off obscure fields that never recur.
    """
    cutoff = datetime.utcnow() - timedelta(days=90)
    deleted = (
        db.query(UserFieldAnswer)
        .filter(UserFieldAnswer.used_count == 1)
        .filter(UserFieldAnswer.last_used < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"deleted": deleted}


def run_cleanup() -> dict:
    """Run cleanup using a new DB session."""
    db = SessionLocal()
    try:
        return cleanup_stale_field_answers(db)
    except Exception as e:
        db.rollback()
        return {"error": str(e), "deleted": 0}
    finally:
        db.close()
