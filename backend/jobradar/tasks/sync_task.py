from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from google.genai.errors import ClientError

JOB_KEYWORDS = [
    "applied", "application", "interview", "offer", "rejected",
    "shortlisted", "hiring", "recruiter", "next steps", "assessment",
    "moving forward", "thank you for applying", "job offer",
]
CONFIDENCE_THRESHOLD = 0.75


def _parse_date(date_str: str) -> datetime:
    try:
        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


def _matches_job_keywords(messages: list[dict]) -> bool:
    last = messages[-1]
    text = (last.get("body", "") + " " + last.get("subject", "")).lower()
    return any(kw in text for kw in JOB_KEYWORDS)


def sync_user_emails(user_id: int, from_date: str = None, to_date: str = None):
    """
    Full Gmail sync pipeline for one user.
    Runs as a FastAPI BackgroundTask — creates its own DB session.
    """
    from backend.app.db.session import SessionLocal
    from backend.app.models.user import User
    from backend.jobradar.models.application import Application, StatusHistory, SyncStatus
    from backend.app.services.google_oauth import get_credentials_for_user
    from backend.jobradar.services.gmail_service import search_threads_by_date, get_thread_messages
    from backend.jobradar.services.classifier import classify_thread
    from backend.jobradar.services.nudge_engine import generate_nudge

    db = SessionLocal()
    try:
        # Resolve user
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.google_access_token:
            _set_status(db, user_id, "error")
            return

        # Safety Fallback: Default to last 2 days if no dates provided at all
        if not from_date and not to_date:
            from_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
            print(f"SYNC: No range provided for user {user_id}. Defaulting to safe 2-day window ({from_date}).")

        try:
            creds = get_credentials_for_user(db, user)
        except Exception:
            _set_status(db, user_id, "error")
            return

        # Step 1 — broad Gmail date-range search
        threads = search_threads_by_date(creds, from_date=from_date, to_date=to_date)
        thread_ids = [t["id"] for t in threads]
        total = len(thread_ids)

        sync = db.query(SyncStatus).filter(SyncStatus.user_id == user_id).first()
        sync.total_threads = total
        sync.last_updated = datetime.utcnow()
        db.commit()

        if not thread_ids or _is_stopped(db, user_id):
            _set_status(db, user_id, "completed" if not thread_ids else "stopped")
            return

        # Step 2 — build lookup of already-tracked threads
        existing = db.query(Application).filter(Application.user_id == user_id).all()
        known = {app.email_thread_id: app for app in existing if app.email_thread_id}

        parsed_count = ai_count = ai_success_count = 0
        quota_exhausted = False

        for i, thread_id in enumerate(thread_ids):
            if quota_exhausted or _is_stopped(db, user_id):
                break

            try:
                messages = get_thread_messages(creds, thread_id)
                if not messages:
                    parsed_count += 1
                    continue

                is_tracked = thread_id in known
                matches_kw = _matches_job_keywords(messages)
                parsed_count += 1

                # Pre-filter: skip if not job-related and not already tracked
                if not matches_kw and not is_tracked:
                    if i % 10 == 0:
                        _update_progress(db, user_id, parsed_count, ai_count, ai_success_count)
                    continue

                last_msg = messages[-1]

                # Skip if the last seen email hasn't changed for tracked apps
                if is_tracked:
                    app_row = known[thread_id]
                    latest_hist = (
                        db.query(StatusHistory)
                        .filter(StatusHistory.application_id == app_row.id)
                        .order_by(StatusHistory.changed_at.desc())
                        .first()
                    )
                    if latest_hist and latest_hist.raw_email_id == last_msg["id"]:
                        if i % 5 == 0:
                            _update_progress(db, user_id, parsed_count, ai_count, ai_success_count)
                        continue

                # AI classification
                ai_count += 1
                _update_progress(db, user_id, parsed_count, ai_count, ai_success_count)

                result = classify_thread(messages)
                if result is None:
                    continue

                ai_success_count += 1
                last_activity = _parse_date(last_msg["date"])

                if is_tracked:
                    app_row = known[thread_id]
                    app_row.last_activity = last_activity
                    app_row.next_action = result.next_action
                    app_row.low_confidence = result.confidence < CONFIDENCE_THRESHOLD
                    app_row.interview_process = result.interview_process

                    if result.status and result.status != app_row.current_status:
                        app_row.current_status = result.status
                        db.add(StatusHistory(
                            application_id=app_row.id,
                            status=result.status,
                            raw_email_id=last_msg["id"],
                            summary=result.summary,
                            changed_at=datetime.utcnow(),
                        ))
                        # Trigger AI nudge for status change
                        # generate_nudge(db, user_id, app_row.id, app_row.company, app_row.role, result.status, is_new=False)
                else:
                    new_app = Application(
                        user_id=user_id,
                        company=result.company or "Unknown",
                        role=result.role or "Unknown Role",
                        platform=result.platform,
                        current_status=result.status or "applied",
                        applied_date=_parse_date(messages[0]["date"]),
                        last_activity=last_activity,
                        next_action=result.next_action,
                        confidence=result.confidence,
                        low_confidence=result.confidence < CONFIDENCE_THRESHOLD,
                        email_thread_id=thread_id,
                        interview_process=result.interview_process,
                        created_at=datetime.utcnow(),
                    )
                    db.add(new_app)
                    db.flush()
                    db.add(StatusHistory(
                        application_id=new_app.id,
                        status=new_app.current_status,
                        raw_email_id=last_msg["id"],
                        summary=result.summary,
                        changed_at=datetime.utcnow(),
                    ))
                    # Trigger AI nudge for new application
                    # generate_nudge(db, user_id, new_app.id, new_app.company, new_app.role, new_app.current_status, is_new=True)

                db.commit()

            except ClientError as e:
                if e.status_code == 429: quota_exhausted = True
            except Exception:
                continue
            finally:
                import time
                time.sleep(4.5)

        final_status = "stopped" if _is_stopped(db, user_id) else ("error" if quota_exhausted else "completed")
        _update_progress(db, user_id, parsed_count, ai_count, ai_success_count, status=final_status)

        user.updated_at = datetime.utcnow()
        db.commit()

    except Exception:
        _set_status(db, user_id, "error")
    finally:
        db.close()


# ── helpers ────────────────────────────────────────────────────────────────

def _is_stopped(db, user_id: int) -> bool:
    from backend.jobradar.models.application import SyncStatus
    row = db.query(SyncStatus).filter(SyncStatus.user_id == user_id).first()
    return row is not None and row.status == "stopped"


def _set_status(db, user_id: int, status: str):
    from backend.jobradar.models.application import SyncStatus
    row = db.query(SyncStatus).filter(SyncStatus.user_id == user_id).first()
    if row:
        row.status = status
        row.last_updated = datetime.utcnow()
        db.commit()


def _update_progress(db, user_id: int, parsed: int, ai: int, ai_success: int, status: str = "running"):
    from backend.jobradar.models.application import SyncStatus
    row = db.query(SyncStatus).filter(SyncStatus.user_id == user_id).first()
    if row:
        row.parsed_count = parsed
        row.ai_count = ai
        row.ai_success_count = ai_success
        row.status = status
        row.last_updated = datetime.utcnow()
        db.commit()
