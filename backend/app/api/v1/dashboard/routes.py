"""
Dashboard API - merged summary (stats, recent applications, companies viewed, applications by day)
"""
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.user import User
from backend.app.models.user_job import UserJob
from backend.app.models.career_page_visit import CareerPageVisit
from backend.app.utils import cache

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

APPLIED_STATUSES = frozenset({
    "applied", "interview", "closed",
    "Applied", "Interviewing", "Offer", "Rejected", "Withdrawn",
})


def _normalize_status(raw: str | None) -> str:
    if not raw or not str(raw).strip():
        return "saved"
    s = str(raw).strip().lower()
    legacy = {
        "i have not yet applied": "saved", "not yet applied": "saved",
        "applied": "applied", "interviewing": "interview",
        "offer": "closed", "rejected": "closed", "withdrawn": "closed",
    }
    return legacy.get(s, s if s in ("saved", "applied", "interview", "closed") else "saved")


def _derive_company_from_url(page_url: str | None) -> str:
    try:
        host = (urlparse(page_url or "").netloc or "").lower().replace("www.", "")
        parts = [p for p in host.split(".") if p and p not in ("com", "io", "co", "org", "net")]
        skip = {"jobs", "careers", "career", "www", "apply", "job"}
        for p in parts:
            if p not in skip and len(p) > 1:
                return p
        return parts[0] if parts else "Unknown"
    except Exception:
        return "Unknown"


def _build_dashboard_summary(db: Session, user_id: int, limit: int, days: int) -> dict:
    """Build full dashboard summary from DB queries."""
    # Stats
    jobs_applied = (
        db.query(UserJob)
        .filter(UserJob.user_id == user_id, UserJob.application_status.in_(APPLIED_STATUSES))
        .count()
    )
    jobs_saved = db.query(UserJob).filter(UserJob.user_id == user_id).count()
    all_companies = set()
    for row in db.query(CareerPageVisit.company_name, CareerPageVisit.page_url).filter(
        CareerPageVisit.user_id == user_id
    ).all():
        name = (row[0] or "").strip()
        if not name and row[1]:
            try:
                host = urlparse(row[1]).netloc or ""
                name = host.replace("www.", "").split(".")[0] if host else ""
            except Exception:
                pass
        if name:
            all_companies.add(name.lower())
    for row in db.query(UserJob.company).filter(UserJob.user_id == user_id).distinct().all():
        if row[0]:
            all_companies.add((row[0] or "").strip().lower())
    companies_checked = len(all_companies)

    # Recent applications
    recent_jobs = (
        db.query(UserJob)
        .filter(UserJob.user_id == user_id, UserJob.application_status.in_(APPLIED_STATUSES))
        .order_by(UserJob.created_at.desc())
        .limit(limit)
        .all()
    )
    recent_applications = [
        {
            "id": j.id,
            "title": j.position_title or "Untitled",
            "company": j.company or "",
            "location": j.location or "",
            "application_status": _normalize_status(j.application_status),
            "job_posting_url": j.job_posting_url,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in recent_jobs
    ]

    # Companies viewed
    rows = (
        db.query(CareerPageVisit.company_name, CareerPageVisit.page_url, CareerPageVisit.created_at)
        .filter(CareerPageVisit.user_id == user_id)
        .order_by(CareerPageVisit.created_at.desc())
        .limit(limit * 3)
        .all()
    )
    seen = set()
    companies_viewed = []
    for r in rows:
        name = (r.company_name or "").strip()
        if not name:
            name = _derive_company_from_url(r.page_url)
        key = name.lower()
        if key not in seen and name:
            seen.add(key)
            companies_viewed.append({"company_name": name, "page_url": r.page_url or ""})
            if len(companies_viewed) >= limit:
                break

    # Applications by day
    cutoff = datetime.utcnow() - timedelta(days=days)
    day_rows = (
        db.query(func.date(UserJob.created_at).label("d"), func.count(UserJob.id).label("c"))
        .filter(
            UserJob.user_id == user_id,
            UserJob.application_status.in_(APPLIED_STATUSES),
            UserJob.created_at >= cutoff,
        )
        .group_by(func.date(UserJob.created_at))
        .order_by(func.date(UserJob.created_at))
        .all()
    )
    applications_by_day = [{"date": str(row[0]), "count": row[1]} for row in day_rows]

    return {
        "stats": {
            "jobs_applied": jobs_applied,
            "jobs_saved": jobs_saved,
            "companies_checked": companies_checked,
        },
        "recent_applications": recent_applications,
        "companies_viewed": companies_viewed,
        "applications_by_day": applications_by_day,
    }


@router.get("/summary")
async def get_dashboard_summary(
    limit: int | None = None,
    days: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Merged dashboard: stats, recent applications, companies viewed, applications by day.
    Cached per user (ttl from config).
    """
    limit_val = limit if limit is not None else settings.dashboard_default_limit
    days_val = days if days is not None else settings.dashboard_default_days
    user_id = current_user.id
    cache_key = f"dashboard_summary:{user_id}"

    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        pass

    result = _build_dashboard_summary(db, user_id, limit_val, days_val)

    try:
        await cache.set(cache_key, result, ttl=settings.dashboard_summary_cache_ttl)
    except Exception:
        pass

    return result
