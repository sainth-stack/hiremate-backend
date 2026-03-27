"""
Periodic cleanup: remove stale one-off user_field_answers entries and expired tailor contexts.
Run via cron or: python -c "from backend.app.tasks.cleanup import run_cleanup; print(run_cleanup())"
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.app.core.logging_config import get_logger
from backend.app.db.session import SessionLocal
from backend.app.models.form_field_learning import UserFieldAnswer
from backend.app.models.tailor_context import TailorContext

logger = get_logger("tasks.cleanup")


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


def cleanup_expired_tailor_contexts(db: Session) -> dict:
    """Delete tailor contexts that have passed their expires_at TTL."""
    deleted = (
        db.query(TailorContext)
        .filter(TailorContext.expires_at < datetime.utcnow())
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info("Cleaned up %d expired tailor contexts", deleted)
    return {"deleted": deleted}


def run_cleanup() -> dict:
    """Run all cleanup tasks using a new DB session."""
    db = SessionLocal()
    try:
        field_result = cleanup_stale_field_answers(db)
        context_result = cleanup_expired_tailor_contexts(db)
        return {
            "stale_field_answers_deleted": field_result["deleted"],
            "expired_tailor_contexts_deleted": context_result["deleted"],
        }
    except Exception as e:
        db.rollback()
        logger.error("Cleanup failed: %s", e)
        return {"error": str(e)}
    finally:
        db.close()
