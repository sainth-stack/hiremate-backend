"""
sentinel.py — The Intelligent Gmail Sentinel Agent

This service is called when a Gmail Push Notification arrives.
It fetches new emails, classifies them with the LLM, and persists
job application data to Supabase.
"""
import threading
from datetime import datetime, timezone

from backend.app.services.google_oauth import get_credentials_for_user

# Per-user locks — only one push processed at a time per user
_user_locks: dict[str, threading.Lock] = {}
_locks_mutex = threading.Lock()


def _get_user_lock(email: str) -> threading.Lock:
    with _locks_mutex:
        if email not in _user_locks:
            _user_locks[email] = threading.Lock()
        return _user_locks[email]
from backend.app.db.session import SessionLocal
from backend.jobradar.services.gmail_service import (
    get_incremental_messages,
    get_thread_by_message,
    get_thread_messages,
)
from backend.jobradar.services.classifier import classify_thread


def process_push_notification(email_address: str, history_id: str):
    """
    Entry point called by the webhook handler.
    Looks up the user, fetches new emails, classifies them, and saves results.
    """
    from backend.app.models.user import User

    lock = _get_user_lock(email_address)
    if not lock.acquire(blocking=False):
        print(f"SENTINEL: Push already in progress for {email_address}. Dropping duplicate.")
        return

    db = SessionLocal()
    try:
        # 1. Find the user by email
        user = db.query(User).filter(User.email == email_address).first()
        if not user:
            print(f"SENTINEL: User not found for {email_address}")
            return

        user_id = user.id
        last_history_id = user.last_history_id

        if not last_history_id:
            print(f"SENTINEL: No last_history_id for user {email_address}. Storing current and exiting.")
            user.last_history_id = history_id
            db.commit()
            return

        # Guard: skip stale pushes (duplicate delivery or queued-while-down with old ID)
        if int(history_id) <= int(last_history_id):
            print(f"SENTINEL: Stale push ({history_id} <= {last_history_id}). Skipping.")
            return

        # Advance the cursor immediately so a crash mid-run won't reprocess the same window
        user.last_history_id = history_id
        db.commit()

        # 2. Load credentials
        try:
            creds = get_credentials_for_user(db, user)
        except Exception as e:
            print(f"SENTINEL: Could not load credentials for {user_id}: {e}")
            return

        # 3. Fetch new message IDs since last known historyId
        try:
            message_ids = get_incremental_messages(creds, last_history_id)
        except Exception as e:
            print(f"SENTINEL: Error fetching incremental messages: {e}")
            user.last_history_id = history_id
            db.commit()
            return

        print(f"SENTINEL: Found {len(message_ids)} new message(s) for {email_address}")

        # 4. Deduplicate by thread — process each unique thread once
        seen_thread_ids = set()
        for message_id in message_ids:
            try:
                msg_meta = get_thread_by_message(creds, message_id)
                thread_id = msg_meta.get("threadId")
                if not thread_id or thread_id in seen_thread_ids:
                    continue
                seen_thread_ids.add(thread_id)

                # 5. Intelligent Token Guard (Pre-Filter)
                snippet = msg_meta.get("snippet", "").lower()
                subject = ""
                # Extract subject from headers if available
                for header in msg_meta.get("payload", {}).get("headers", []):
                    if header["name"].lower() == "subject":
                        subject = header["value"].lower()
                        break

                # Check if this thread IS ALREADY tracked (always process known jobs)
                from backend.jobradar.models.application import Application
                is_tracked = db.query(Application).filter(
                    Application.email_thread_id == thread_id,
                    Application.user_id == user_id,
                ).first()

                # Keywords that strongly suggest a job context
                job_keywords = [
                    # Application stage
                    "applied", "application", "thank you for applying", "we received your",
                    # Positive outcomes
                    "congratulations", "selected", "you have been selected", "happy to inform",
                    "pleased to inform", "excited to offer", "job offer", "offer letter",
                    "welcome aboard", "onboarding", "joining date", "start date",
                    # Interview signals
                    "interview", "assessment", "assignment", "test", "coding challenge",
                    "technical round", "next steps", "next round", "schedule a call",
                    # Recruiter signals
                    "recruiter", "hiring", "talent", "opportunity", "position", "role",
                    # Rejection / status signals
                    "rejected", "not moving forward", "not selected", "unfortunately",
                    "shortlisted", "in review", "under review", "moving forward",
                ]
                matches_keywords = any(kw in snippet or kw in subject for kw in job_keywords)

                if not matches_keywords and not is_tracked:
                    print(f"SENTINEL: Skipping non-job email in thread {thread_id} (No keywords matched and not tracked).")
                    continue

                # 6. Fetch all messages in this thread
                messages = get_thread_messages(creds, thread_id)
                if not messages:
                    continue

                # 7. Classify the thread with AI
                result = classify_thread(messages)
                if result is None:
                    print(f"SENTINEL: Thread {thread_id} is not job-related (AI confirmed).")
                    continue

                print(f"SENTINEL: Job detected — {result.company} | {result.role} | {result.status}")

                # 7. Upsert the application into Supabase
                _save_application(db, user_id, thread_id, result, messages)

            except Exception as e:
                print(f"SENTINEL: Error processing message {message_id}: {e}")
                db.rollback()
                continue
            finally:
                import time
                time.sleep(4.5)  # Max ~13 requests per minute (Free Tier limit is 15 RPM)

        print(f"SENTINEL: Done. historyId already advanced to {history_id}")

    except Exception as e:
        db.rollback()
    finally:
        db.close()
        lock.release()


def _save_application(db, user_id: int, thread_id: str, result, messages: list):
    """
    Upsert a classified thread as a job application.
    If the thread already exists, update the status and add history.
    """
    from backend.jobradar.models.application import Application, StatusHistory

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Direct check: exact threadId match
    existing = db.query(Application).filter(
        Application.email_thread_id == thread_id,
        Application.user_id == user_id,
    ).first()

    # 2. Logic-based check: same company + similar role (if threadId didn't match)
    if not existing and result.company and result.role:
        normalized_company = result.company.lower().strip()
        
        # Find potential matches for the same user and company
        potential_matches = db.query(Application).filter(
            Application.user_id == user_id,
            Application.company.ilike(f"%{normalized_company}%")
        ).all()

        for potential in potential_matches:
            p_role = (potential.role or "").lower().strip()
            r_role = (result.role or "").lower().strip()
            
            # Match if one is a substring of the other OR they share significant words
            if p_role in r_role or r_role in p_role:
                existing = potential
                print(f"SENTINEL: Resolved duplicate! Thread {thread_id} matched existing app {existing.id} ({existing.company}) via role similarity.")
                break
            
            # Word-based overlap (at least 70% of words in the shorter role must be in the longer one)
            p_words = set(p_role.split())
            r_words = set(r_role.split())
            if not p_words or not r_words: continue
            
            common = p_words.intersection(r_words)
            shorter_len = min(len(p_words), len(r_words))
            if len(common) / shorter_len >= 0.7:
                existing = potential
                print(f"SENTINEL: Resolved duplicate! Thread {thread_id} matched existing app {existing.id} ({existing.company}) via word overlap.")
                break

    if existing:
        # Update always if status has changed OR if we found a match from a different thread
        status_changed = existing.current_status != result.status
        is_new_thread = existing.email_thread_id != thread_id

        if status_changed or is_new_thread:
            # We don't overwrite the original email_thread_id as it's a unique field in the DB
            # but we update the metadata to reflect the most recent signal
            existing.current_status = result.status or existing.current_status
            existing.last_activity = now
            existing.next_action = result.next_action or existing.next_action
            existing.confidence = result.confidence or existing.confidence
            existing.interview_process = result.interview_process or existing.interview_process

            db.add(StatusHistory(
                application_id=existing.id,
                status=result.status or existing.current_status,
                summary=result.summary,
                changed_at=now,
            ))
            db.commit()
            print(f"SENTINEL: Updated existing application {existing.id} → {result.status} (Thread: {thread_id})")
        else:
            print(f"SENTINEL: No changes for application {existing.id}. Skipping update.")
    else:
        # New application — insert it
        subject = messages[0].get("subject", "Unknown Role") if messages else "Unknown Role"
        new_app = Application(
            user_id=user_id,
            company=result.company or "Unknown",
            role=result.role or subject,
            platform=result.platform,
            current_status=result.status or "applied",
            applied_date=now,
            last_activity=now,
            next_action=result.next_action,
            confidence=result.confidence,
            low_confidence=result.confidence < 0.6,
            email_thread_id=thread_id,
            interview_process=result.interview_process,
            created_at=now,
        )
        db.add(new_app)
        db.flush()

        db.add(StatusHistory(
            application_id=new_app.id,
            status=result.status or "applied",
            summary=result.summary,
            changed_at=now,
        ))
        db.commit()
        print(f"SENTINEL: Created new application {new_app.id} for {result.company}")
