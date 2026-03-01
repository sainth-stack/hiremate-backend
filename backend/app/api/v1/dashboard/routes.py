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


def _parse_date(d: str | None):
    """Parse YYYY-MM-DD string to datetime at midnight UTC."""
    if not d:
        return None
    try:
        return datetime.strptime(d.strip()[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _build_dashboard_summary(
    db: Session,
    user_id: int,
    limit: int,
    cutoff_start: datetime | None,
    cutoff_end: datetime | None,
) -> dict:
    """Build full dashboard summary from DB queries. Filter by cutoff_start/end when provided."""
    base_user = UserJob.user_id == user_id
    base_visit = CareerPageVisit.user_id == user_id

    # Build date filters
    job_date_filter = []
    if cutoff_start:
        job_date_filter.append(UserJob.created_at >= cutoff_start)
    if cutoff_end:
        job_date_filter.append(UserJob.created_at <= cutoff_end)
    visit_date_filter = []
    if cutoff_start:
        visit_date_filter.append(CareerPageVisit.created_at >= cutoff_start)
    if cutoff_end:
        visit_date_filter.append(CareerPageVisit.created_at <= cutoff_end)

    # Stats (filtered by date when range provided)
    jobs_applied_q = (
        db.query(UserJob)
        .filter(base_user, UserJob.application_status.in_(APPLIED_STATUSES))
    )
    jobs_saved_q = db.query(UserJob).filter(base_user)
    for f in job_date_filter:
        jobs_applied_q = jobs_applied_q.filter(f)
        jobs_saved_q = jobs_saved_q.filter(f)
    jobs_applied = jobs_applied_q.count()
    jobs_saved = jobs_saved_q.count()

    all_companies = set()
    visit_q = db.query(CareerPageVisit.company_name, CareerPageVisit.page_url).filter(base_visit)
    for f in visit_date_filter:
        visit_q = visit_q.filter(f)
    for row in visit_q.all():
        name = (row[0] or "").strip()
        if not name and row[1]:
            try:
                host = urlparse(row[1]).netloc or ""
                name = host.replace("www.", "").split(".")[0] if host else ""
            except Exception:
                pass
        if name:
            all_companies.add(name.lower())
    job_company_q = db.query(UserJob.company).filter(base_user).distinct()
    for f in job_date_filter:
        job_company_q = job_company_q.filter(f)
    for row in job_company_q.all():
        if row[0]:
            all_companies.add((row[0] or "").strip().lower())
    companies_checked = len(all_companies)

    # Recent applications
    recent_jobs_q = (
        db.query(UserJob)
        .filter(base_user, UserJob.application_status.in_(APPLIED_STATUSES))
    )
    for f in job_date_filter:
        recent_jobs_q = recent_jobs_q.filter(f)
    recent_jobs = recent_jobs_q.order_by(UserJob.created_at.desc()).limit(limit).all()
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

    # Companies viewed — aggregate by company: visit_count, last_visited_at
    companies_viewed_q = (
        db.query(CareerPageVisit.company_name, CareerPageVisit.page_url, CareerPageVisit.created_at)
        .filter(base_visit)
    )
    for f in visit_date_filter:
        companies_viewed_q = companies_viewed_q.filter(f)
    rows = companies_viewed_q.order_by(CareerPageVisit.created_at.desc()).limit(limit * 5).all()
    agg = {}  # key -> {company_name, page_url, visit_count, last_visited_at}
    for r in rows:
        name = (r.company_name or "").strip()
        if not name:
            name = _derive_company_from_url(r.page_url)
        key = name.lower()
        if not name:
            continue
        if key not in agg:
            agg[key] = {
                "company_name": name,
                "page_url": r.page_url or "",
                "visit_count": 0,
                "last_visited_at": None,
            }
        agg[key]["visit_count"] += 1
        if r.created_at and (
            agg[key]["last_visited_at"] is None
            or r.created_at > agg[key]["last_visited_at"]
        ):
            agg[key]["last_visited_at"] = r.created_at
    companies_viewed = sorted(
        agg.values(),
        key=lambda x: (x["last_visited_at"] or datetime.min).isoformat(),
        reverse=True,
    )[:limit]
    for c in companies_viewed:
        if c["last_visited_at"]:
            c["last_visited_at"] = c["last_visited_at"].isoformat()

    # Applications by day
    day_filter = [
        base_user,
        UserJob.application_status.in_(APPLIED_STATUSES),
    ]
    if cutoff_start:
        day_filter.append(UserJob.created_at >= cutoff_start)
    if cutoff_end:
        day_filter.append(UserJob.created_at <= cutoff_end)
    day_rows = (
        db.query(func.date(UserJob.created_at).label("d"), func.count(UserJob.id).label("c"))
        .filter(*day_filter)
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
    from_date: str | None = None,
    to_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Merged dashboard: stats, recent applications, companies viewed, applications by day.
    Use days (e.g. 7 for last 7 days) or from_date/to_date (YYYY-MM-DD) for custom range.
    Cached per user+range (ttl from config).
    """
    limit_val = limit if limit is not None else settings.dashboard_default_limit
    user_id = current_user.id
    now = datetime.utcnow()
    cutoff_start = None
    cutoff_end = None

    if from_date or to_date:
        # Custom date range
        cutoff_start = _parse_date(from_date) if from_date else datetime(2000, 1, 1)
        cutoff_end = _parse_date(to_date) if to_date else now
        if cutoff_end:
            cutoff_end = datetime(
                cutoff_end.year, cutoff_end.month, cutoff_end.day, 23, 59, 59
            )
    else:
        # Preset: last N days
        days_val = days if days is not None else settings.dashboard_default_days
        cutoff_start = now - timedelta(days=days_val)
        cutoff_end = now

    start_str = cutoff_start.strftime("%Y-%m-%d") if cutoff_start else ""
    end_str = cutoff_end.strftime("%Y-%m-%d") if cutoff_end else ""
    cache_key = f"dashboard_summary:{user_id}:{start_str}:{end_str}"

    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        pass

    result = _build_dashboard_summary(
        db, user_id, limit_val, cutoff_start, cutoff_end
    )

    try:
        await cache.set(cache_key, result, ttl=settings.dashboard_summary_cache_ttl)
    except Exception:
        pass

    return result
