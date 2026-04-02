from backend.app.db.session import SessionLocal
from backend.app.models.user import User
from backend.app.services.google_oauth import get_credentials_for_user
from backend.jobradar.services.gmail_service import get_thread_messages, search_threads
from backend.jobradar.models.application import Application


def fetch_raw_email(user_id: str, company_name: str) -> str:
    """
    Agentic Tool: Fetches the full text of the most recent email thread
    for a specific company from the user's Gmail inbox.
    """
    db = SessionLocal()
    try:
        apps = db.query(Application).filter(
            Application.user_id == user_id,
            Application.company.ilike(f"%{company_name}%"),
        ).all()

        if not apps:
            return f"No tracked application found for '{company_name}' in the database."

        # Pick the most recently active application
        app = sorted(apps, key=lambda a: a.last_activity or a.applied_date, reverse=True)[0]
        thread_id = app.email_thread_id

        if not thread_id:
            return f"Found the application for {app.company} but no email thread is linked to it."

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "Authentication Error: User not found."

        try:
            creds = get_credentials_for_user(db, user)
        except Exception as e:
            return f"Authentication Error: Could not load Gmail credentials. {e}"

        try:
            messages = get_thread_messages(creds, thread_id)
        except Exception as e:
            return f"Gmail API Error: Failed to fetch thread {thread_id}. {e}"

        if not messages:
            return f"Found the application for {app.company} but the email thread appears to be empty."

        compiled = []
        for i, msg in enumerate(messages, start=1):
            compiled.append(
                f"--- Email #{i} ---\n"
                f"From: {msg.get('from', 'Unknown')}\n"       # key is 'from', not 'sender'
                f"Date: {msg.get('date', 'Unknown')}\n"
                f"Subject: {msg.get('subject', '')}\n"
                f"Body:\n{msg.get('body', '').strip()}\n"     # key is 'body', not 'snippet'
            )
        return "\n".join(compiled)

    finally:
        db.close()


def search_gmail_inbox(user_id: str, query: str) -> str:
    """
    Agentic Tool: Searches the user's Gmail inbox and returns the full body
    of matching threads (up to 3 threads, most recent first).
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "Authentication Error: User not found."

        try:
            creds = get_credentials_for_user(db, user)
        except Exception as e:
            return f"Authentication Error: Could not load Gmail credentials. {e}"

        try:
            # threads.list returns {id, snippet} — snippet is often empty/truncated,
            # so we fetch the full thread for each result
            threads = search_threads(creds, query, max_results=3)
        except Exception as e:
            return f"Gmail Search Error: {e}"

        if not threads:
            return f"No emails found in Gmail matching: '{query}'."

        results = []
        for thread in threads:
            thread_id = thread.get("id")
            try:
                messages = get_thread_messages(creds, thread_id)
            except Exception:
                continue

            if not messages:
                continue

            # Use subject + body of the most recent message as the result
            latest = messages[-1]
            results.append(
                f"=== Thread: {latest.get('subject', 'No Subject')} ===\n"
                f"From: {latest.get('from', 'Unknown')} · {latest.get('date', '')}\n"
                f"{latest.get('body', '').strip()[:2000]}"
            )

        if not results:
            return f"Found {len(threads)} thread(s) matching '{query}' but could not read their content."

        return f"Found {len(results)} matching thread(s):\n\n" + "\n\n".join(results)

    finally:
        db.close()
