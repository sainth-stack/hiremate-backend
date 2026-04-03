"""
APScheduler background jobs:
- Every 30 minutes: incremental Gmail sync for all users
- Every night at midnight: mark ghosted applications + create nudges
- Every 6 days: renew Gmail Watch subscriptions (they expire after 7 days)
"""
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from backend.app.core.config import settings

scheduler = BackgroundScheduler(timezone="UTC")


def _sync_all_users():
    """Trigger incremental email sync for every user with Google credentials."""
    from backend.app.db.session import SessionLocal
    from backend.app.models.user import User
    from backend.jobradar.tasks.sync_task import sync_user_emails

    db = SessionLocal()
    try:
        users = db.query(User.id).filter(User.google_access_token.isnot(None)).all()
        from_date = (
            datetime.now(timezone.utc) - timedelta(days=settings.default_sync_days)
        ).strftime("%Y-%m-%d")

        for (user_id,) in users:
            try:
                sync_user_emails(user_id, from_date=from_date)
            except Exception:
                pass
    except Exception:
        pass
    finally:
        db.close()


def _mark_ghosted():
    """
    Mark stale applications as ghosted and create a nudge for each.
    Runs nightly at midnight UTC.
    """
    from backend.app.db.session import SessionLocal
    from backend.jobradar.models.application import Application, StatusHistory
    from backend.jobradar.models.nudge import Nudge

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.ghosted_days)
        active_statuses = ["applied", "acknowledged", "in_review", "interview_completed"]

        for status in active_statuses:
            apps = (
                db.query(Application)
                .filter(
                    Application.current_status == status,
                    Application.last_activity < cutoff,
                )
                .all()
            )
            if not apps:
                continue

            for app in apps:
                app.current_status = "ghosted"
                db.add(StatusHistory(
                    application_id=app.id,
                    status="ghosted",
                    summary=f"No response in {settings.ghosted_days}+ days — automatically marked as ghosted.",
                    changed_at=datetime.utcnow(),
                ))
                db.add(Nudge(
                    user_id=app.user_id,
                    application_id=app.id,
                    message=(
                        f"No response from {app.company} ({app.role}) "
                        f"in {settings.ghosted_days}+ days. "
                        "Consider sending a follow-up or moving on."
                    ),
                    nudge_type="ghosted",
                    is_read=False,
                ))

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    # from jobradar.services.gmail_service import renew_watches_for_all_users

    # scheduler.add_job(_sync_all_users, "interval", minutes=30, id="sync_emails")
    # scheduler.add_job(_mark_ghosted, "cron", hour=0, minute=0, id="mark_ghosted")
    # scheduler.add_job(renew_watches_for_all_users, "interval", days=6, id="renew_gmail_watch")
    # scheduler.start()
    pass


def stop_scheduler():
    scheduler.shutdown()
