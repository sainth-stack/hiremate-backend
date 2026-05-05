from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from google.genai.errors import ClientError
from typing import Optional
import re

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


def _extract_domain_from_email(email: str) -> Optional[str]:
    """Extract domain from email address."""
    if not email:
        return None
    match = re.search(r'@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', email)
    return match.group(1).lower() if match else None


def _upsert_company_profile(db, result, last_msg_from: str = None):
    """
    Upsert company profile by domain using enrichment service.
    Returns company_profile_id or None.
    """
    from backend.jobradar.services.company_enrichment_service import enrich_company
    
    # Determine domain
    domain = None
    if result.company_signals and result.company_signals.domain:
        domain = result.company_signals.domain.lower()
    elif last_msg_from:
        domain = _extract_domain_from_email(last_msg_from)
        if domain and domain in ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]:
            domain = None  # Skip personal email domains
    
    if not domain:
        return None
    
    try:
        # Use enrichment service (handles caching and AI enrichment)
        profile = enrich_company(db, domain)
        
        # Update with AI classifier signals if provided
        if result.company_signals:
            updated = False
            if result.company_signals.industry and not profile.industry:
                profile.industry = result.company_signals.industry
                updated = True
            if result.company_signals.size_range and not profile.size_range:
                profile.size_range = result.company_signals.size_range
                updated = True
            if result.company_signals.hq_location and not profile.hq_location:
                profile.hq_location = result.company_signals.hq_location
                updated = True
            if result.company_signals.tech_stack and not profile.tech_stack:
                profile.tech_stack = result.company_signals.tech_stack
                updated = True
            
            if updated:
                db.commit()
                db.refresh(profile)
        
        return profile.id
        
    except Exception as e:
        print(f"Company enrichment failed for {domain}: {e}")
        return None


def _upsert_hr_contacts(db, application_id: int, hr_contacts: list, source_email_id: str = None):
    """Upsert HR contacts for an application (deduplicate by email)."""
    from backend.jobradar.models.application import HRContact
    
    if not hr_contacts:
        return
    
    existing = db.query(HRContact).filter(HRContact.application_id == application_id).all()
    existing_emails = {c.email.lower(): c for c in existing if c.email}
    
    for contact_data in hr_contacts:
        email = contact_data.email.lower() if contact_data.email else None
        
        if email and email in existing_emails:
            contact = existing_emails[email]
            if contact_data.name and not contact.name:
                contact.name = contact_data.name
            if contact_data.linkedin_url and not contact.linkedin_url:
                contact.linkedin_url = contact_data.linkedin_url
            if contact_data.title and not contact.title:
                contact.title = contact_data.title
        else:
            new_contact = HRContact(
                application_id=application_id,
                name=contact_data.name,
                email=contact_data.email,
                linkedin_url=contact_data.linkedin_url,
                title=contact_data.title,
                source_email_id=source_email_id,
                created_at=datetime.utcnow()
            )
            db.add(new_contact)


def _upsert_interview_events(db, application_id: int, interview_events: list) -> list[int]:
    """
    Insert interview events (deduplicate by scheduled_at + event_type).
    Returns list of newly created event IDs for calendar sync.
    """
    from backend.jobradar.models.application import InterviewEvent, EventType, MeetingFormat
    
    if not interview_events:
        return []
    
    existing = db.query(InterviewEvent).filter(InterviewEvent.application_id == application_id).all()
    existing_keys = {
        (e.scheduled_at, e.event_type.value if e.event_type else None) 
        for e in existing
    }
    
    new_event_ids = []
    
    for event_data in interview_events:
        scheduled_at = None
        if event_data.scheduled_at:
            try:
                scheduled_at = datetime.fromisoformat(event_data.scheduled_at.replace('Z', '+00:00')).replace(tzinfo=None)
            except (ValueError, AttributeError):
                pass
        
        event_type_str = event_data.event_type
        event_key = (scheduled_at, event_type_str)
        
        if event_key not in existing_keys:
            try:
                event_type_enum = EventType[event_type_str] if event_type_str else None
            except (KeyError, AttributeError):
                event_type_enum = EventType.interview
            
            format_enum = None
            if event_data.format:
                try:
                    format_val = event_data.format if event_data.format != "async" else "async_format"
                    format_enum = MeetingFormat[format_val]
                except (KeyError, AttributeError):
                    pass
            
            new_event = InterviewEvent(
                application_id=application_id,
                event_type=event_type_enum,
                title=event_data.title,
                scheduled_at=scheduled_at,
                duration_minutes=event_data.duration_minutes,
                format=format_enum,
                meeting_link=event_data.meeting_link,
                notes=event_data.notes,
                created_at=datetime.utcnow()
            )
            db.add(new_event)
            db.flush()
            
            if new_event.id and scheduled_at:
                new_event_ids.append(new_event.id)
    
    return new_event_ids


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
        except Exception as e:
            print(f"SYNC ERROR: Failed to get credentials for user {user_id}: {e}")
            _set_status(db, user_id, "error")
            return

        # Step 1 — broad Gmail date-range search
        print(f"SYNC: Searching emails for user {user_id} from {from_date} to {to_date}")
        threads = search_threads_by_date(creds, from_date=from_date, to_date=to_date)
        thread_ids = [t["id"] for t in threads]
        total = len(thread_ids)
        print(f"SYNC: Found {total} email threads for user {user_id}")

        sync = db.query(SyncStatus).filter(SyncStatus.user_id == user_id).first()
        sync.total_threads = total
        sync.last_updated = datetime.utcnow()
        db.commit()

        if not thread_ids or _is_stopped(db, user_id):
            status = "completed" if not thread_ids else "stopped"
            print(f"SYNC: Ending sync with status={status} (threads={total})")
            _set_status(db, user_id, status)
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
                if not is_tracked:
                    from backend.app.services.usage_service import check_feature_limit
                    allowed, msg = check_feature_limit(db, user, "job_tracking")
                    if not allowed:
                        if i % 10 == 0:
                            _update_progress(db, user_id, parsed_count, ai_count, ai_success_count)
                        continue

                ai_count += 1
                _update_progress(db, user_id, parsed_count, ai_count, ai_success_count)

                result = classify_thread(messages, user_id=user_id, email=user.email)
                if result is None:
                    continue

                ai_success_count += 1
                last_activity = _parse_date(last_msg["date"])
                last_msg_from = last_msg.get("from", "")

                if is_tracked:
                    app_row = known[thread_id]
                    app_row.last_activity = last_activity
                    app_row.next_action = result.next_action
                    app_row.low_confidence = result.confidence < CONFIDENCE_THRESHOLD
                    app_row.interview_process = result.interview_process

                    company_profile_id = _upsert_company_profile(db, result, last_msg_from)
                    if company_profile_id:
                        app_row.company_profile_id = company_profile_id

                    if result.salary_range:
                        if result.salary_range.min:
                            app_row.salary_min = result.salary_range.min
                        if result.salary_range.max:
                            app_row.salary_max = result.salary_range.max
                        if result.salary_range.currency:
                            app_row.salary_currency = result.salary_range.currency

                    _upsert_hr_contacts(db, app_row.id, result.hr_contacts, last_msg["id"])
                    new_event_ids = _upsert_interview_events(db, app_row.id, result.interview_events)
                    
                    # Trigger calendar sync for new events
                    if new_event_ids:
                        for event_id in new_event_ids:
                            _try_create_calendar_event(db, user_id, event_id)

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
                    company_profile_id = _upsert_company_profile(db, result, last_msg_from)
                    
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
                        company_profile_id=company_profile_id,
                        salary_min=result.salary_range.min if result.salary_range else None,
                        salary_max=result.salary_range.max if result.salary_range else None,
                        salary_currency=result.salary_range.currency if result.salary_range else None,
                        created_at=datetime.utcnow(),
                    )
                    db.add(new_app)
                    db.flush()
                    
                    _upsert_hr_contacts(db, new_app.id, result.hr_contacts, last_msg["id"])
                    new_event_ids = _upsert_interview_events(db, new_app.id, result.interview_events)
                    
                    # Trigger calendar sync for new events
                    if new_event_ids:
                        for event_id in new_event_ids:
                            _try_create_calendar_event(db, user_id, event_id)
                    
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

    except Exception as e:
        import traceback
        print(f"SYNC ERROR: Exception in sync_user_emails for user {user_id}: {e}")
        print(f"SYNC ERROR: Traceback: {traceback.format_exc()}")
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


def _try_create_calendar_event(db, user_id: int, event_id: int):
    """
    Try to create a calendar event for a new interview event.
    Silently fails if calendar sync is not available or encounters errors.
    """
    try:
        from backend.jobradar.services.calendar_service import create_calendar_event
        create_calendar_event(db, user_id, event_id)
    except Exception as e:
        print(f"Calendar sync failed for event {event_id}: {e}")
