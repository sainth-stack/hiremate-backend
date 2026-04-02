"""
Gmail API service — thread search, message parsing, push watch management.
Credentials are always obtained via google_oauth.get_credentials_for_user().
"""
import base64
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.app.core.config import settings


def get_gmail_service(creds: Credentials):
    return build("gmail", "v1", credentials=creds)


def search_threads(creds: Credentials, query: str, max_results: int = 10) -> list[dict]:
    """
    Search Gmail threads using a custom query string.
    Returns list of {id, snippet}.
    """
    service = get_gmail_service(creds)
    result = service.users().threads().list(
        userId="me",
        q=query,
        maxResults=max_results,
    ).execute()
    return result.get("threads", [])


def search_threads_by_date(creds: Credentials, from_date: str = None, to_date: str = None) -> list[dict]:
    """
    Search ALL Gmail threads within a date range, paginating through every page.
    Returns list of {id, snippet}.
    """
    service = get_gmail_service(creds)
    query = ""
    if from_date:
        query += f" after:{from_date.replace('-', '/')}"
    if to_date:
        query += f" before:{to_date.replace('-', '/')}"

    threads = []
    next_page_token = None
    while True:
        result = service.users().threads().list(
            userId="me", q=query.strip(), maxResults=100, pageToken=next_page_token
        ).execute()
        threads.extend(result.get("threads", []))
        next_page_token = result.get("nextPageToken")
        if not next_page_token:
            break
    return threads


def get_thread_messages(creds: Credentials, thread_id: str) -> list[dict]:
    """
    Fetch all messages in a thread.
    Returns list of {id, subject, from, date, body}.
    """
    service = get_gmail_service(creds)
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    return [_parse_message(msg) for msg in thread.get("messages", [])]


def get_thread_by_message(creds: Credentials, message_id: str) -> dict:
    """Returns the message metadata including threadId, snippet, and headers."""
    service = get_gmail_service(creds)
    return service.users().messages().get(userId="me", id=message_id, format="metadata").execute()


def get_incremental_messages(creds: Credentials, start_history_id: str) -> list[str]:
    """Fetch IDs of messages added after start_history_id."""
    service = get_gmail_service(creds)
    result = service.users().history().list(
        userId="me",
        startHistoryId=start_history_id,
        historyTypes=["messageAdded"],
    ).execute()

    message_ids = []
    while True:
        for h in result.get("history", []):
            for added in h.get("messagesAdded", []):
                msg = added.get("message", {})
                if msg.get("id"):
                    message_ids.append(msg["id"])
        page_token = result.get("nextPageToken")
        if not page_token:
            break
        result = service.users().history().list(
            userId="me",
            startHistoryId=start_history_id,
            historyTypes=["messageAdded"],
            pageToken=page_token,
        ).execute()

    return list(set(message_ids))


def search_job_threads(creds: Credentials, max_results: int = 100, from_date: str = None, to_date: str = None) -> list[dict]:
    """
    Search Gmail threads with job keywords, optionally restricted by date.
    Dates should be in YYYY-MM-DD or YYYY/MM/DD format.
    """
    service = get_gmail_service(creds)

    query = settings.gmail_search_query
    if from_date:
        query += f" after:{from_date.replace('-', '/')}"
    if to_date:
        query += f" before:{to_date.replace('-', '/')}"

    result = service.users().threads().list(
        userId="me",
        q=query,
        maxResults=max_results,
    ).execute()
    return result.get("threads", [])


def get_thread_latest_message_id(creds: Credentials, thread_id: str) -> str | None:
    """Return the ID of the most recent message in a thread."""
    service = get_gmail_service(creds)
    thread = service.users().threads().get(
        userId="me", id=thread_id, format="metadata",
        metadataHeaders=["Subject"],
    ).execute()
    msgs = thread.get("messages", [])
    return msgs[-1]["id"] if msgs else None


def get_latest_history_id(creds: Credentials) -> str | None:
    """Gets the latest historyId for the user's mailbox."""
    service = get_gmail_service(creds)
    profile = service.users().getProfile(userId="me").execute()
    return profile.get("historyId")


def subscribe_to_watch(creds: Credentials) -> dict | None:
    """
    Register a push notification watch on the user's inbox.
    Requires gmail_push_topic to be set in settings.
    """
    if not settings.gmail_push_topic:
        return None

    service = get_gmail_service(creds)
    body = {
        "labelIds": ["INBOX"],
        "topicName": settings.gmail_push_topic,
        "labelFilterAction": "include",
    }
    return service.users().watch(userId="me", body=body).execute()


def stop_watch(creds: Credentials):
    """Stop the push notification watch."""
    service = get_gmail_service(creds)
    service.users().stop(userId="me").execute()


def renew_watches_for_all_users():
    """
    Called by the scheduler every 6 days.
    Loops through all DB users and renews their Gmail watch.
    """
    from backend.app.db.session import SessionLocal
    from backend.app.models.user import User
    from backend.app.services.google_oauth import get_credentials_for_user

    db = SessionLocal()
    try:
        users = db.query(User).filter(User.google_access_token.isnot(None)).all()
        for user in users:
            try:
                creds = get_credentials_for_user(db, user)
                subscribe_to_watch(creds)
            except Exception:
                pass
    except Exception:
        pass
    finally:
        db.close()


def _parse_message(msg: dict) -> dict:
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    body = _extract_body(msg["payload"])
    return {
        "id":      msg["id"],
        "subject": headers.get("Subject", ""),
        "from":    headers.get("From", ""),
        "date":    headers.get("Date", ""),
        "body":    body[:4000],  # cap at 4k chars to control token usage
    }


def _extract_body(payload: dict) -> str:
    """Recursively extract plain-text body from a MIME payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        raw = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        return re.sub(r"<[^>]+>", " ", raw)
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result.strip():
            return result
    return ""
