"""
DB-backed storage for Tailor Resume context from extension.
When user clicks "Tailor Resume" on a job page, we store JD + title in DB;
resume-generator fetches and clears on next request.
Replaces the previous in-memory _store dict which did not survive server restarts.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.tailor_context import TailorContext

_DEFAULT_TTL_HOURS = 4


def set_tailor_context(
    db: Session,
    user_id: int,
    job_description: str,
    job_title: str = "",
    url: str = "",
    job_id: int | None = None,
    source: str = "extension",
) -> TailorContext:
    """Create tailor context with 4-hour TTL. Cleans up expired contexts for the user first."""
    # Remove stale contexts for this user before inserting a new one
    db.query(TailorContext).filter(
        TailorContext.user_id == user_id,
        TailorContext.expires_at < datetime.utcnow(),
    ).delete(synchronize_session=False)

    context = TailorContext(
        user_id=user_id,
        job_id=job_id,
        job_description=job_description or "",
        job_title=(job_title or "").strip(),
        source=source,
        expires_at=datetime.utcnow() + timedelta(hours=_DEFAULT_TTL_HOURS),
    )
    db.add(context)
    db.commit()
    return context


def get_and_clear_tailor_context(db: Session, user_id: int) -> dict[str, Any] | None:
    """Fetch the most recent non-expired tailor context for the user and delete it."""
    context = (
        db.query(TailorContext)
        .filter(
            TailorContext.user_id == user_id,
            TailorContext.expires_at >= datetime.utcnow(),
        )
        .order_by(TailorContext.created_at.desc())
        .first()
    )
    if not context:
        return None

    result: dict[str, Any] = {
        "job_id": context.job_id,
        "job_description": context.job_description,
        "job_title": context.job_title or "",
        "url": "",
        "source": context.source or "extension",
    }
    db.delete(context)
    db.commit()
    return result
