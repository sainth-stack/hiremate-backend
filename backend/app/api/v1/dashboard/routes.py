"""
Dashboard API - stats, recent applications
"""
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.user import User
from backend.app.models.user_job import UserJob
from backend.app.models.career_page_visit import CareerPageVisit

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Statuses that count as "applied" (past saved stage) - include legacy for backwards compat
APPLIED_STATUSES = frozenset({
    "applied", "interview", "closed",
    "Applied", "Interviewing", "Offer", "Rejected", "Withdrawn",
})


def _normalize_status(raw: str | None) -> str:
    """Map legacy status to canonical (saved, applied, interview, closed)."""
    if not raw or not str(raw).strip():
        return "saved"
    s = str(raw).strip().lower()
    legacy = {
        "i have not yet applied": "saved", "not yet applied": "saved",
        "applied": "applied", "interviewing": "interview",
        "offer": "closed", "rejected": "closed", "withdrawn": "closed",
    }
    return legacy.get(s, s if s in ("saved", "applied", "interview", "closed") else "saved")


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns summary stats for dashboard:
    - jobs_applied: count of user_jobs where application_status is Applied/Interviewing/Offer/Rejected/Withdrawn
    - jobs_saved: total count of user_jobs
    - companies_checked: distinct companies from career_page_visits + user_jobs
    """
    user_id = current_user.id

    jobs_applied = (
        db.query(UserJob)
        .filter(UserJob.user_id == user_id, UserJob.application_status.in_(APPLIED_STATUSES))
        .count()
    )

    jobs_saved = db.query(UserJob).filter(UserJob.user_id == user_id).count()

    # Companies from career_page_visits and user_jobs (distinct, derive from URL when company_name null)
    from urllib.parse import urlparse

    all_companies = set()
    for row in db.query(CareerPageVisit.company_name, CareerPageVisit.page_url).filter(CareerPageVisit.user_id == user_id).all():
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

    return {
        "jobs_applied": jobs_applied,
        "jobs_saved": jobs_saved,
        "companies_checked": companies_checked,
    }


@router.get("/companies-viewed")
def get_companies_viewed(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Companies from career page visits - for Companies Viewed box. Returns company_name and most recent page_url."""
    rows = (
        db.query(CareerPageVisit.company_name, CareerPageVisit.page_url, CareerPageVisit.created_at)
        .filter(CareerPageVisit.user_id == current_user.id)
        .order_by(CareerPageVisit.created_at.desc())
        .limit(limit * 3)
        .all()
    )
    seen = set()
    result = []
    def _derive_company_from_url(page_url):
        try:
            from urllib.parse import urlparse
            host = (urlparse(page_url or "").netloc or "").lower().replace("www.", "")
            parts = [p for p in host.split(".") if p and p not in ("com", "io", "co", "org", "net")]
            skip = {"jobs", "careers", "career", "www", "apply", "job"}
            for p in parts:
                if p not in skip and len(p) > 1:
                    return p
            return parts[0] if parts else "Unknown"
        except Exception:
            return "Unknown"

    for r in rows:
        name = (r.company_name or "").strip()
        if not name:
            name = _derive_company_from_url(r.page_url)
        key = name.lower()
        if key not in seen and name:
            seen.add(key)
            result.append({"company_name": name, "page_url": r.page_url or ""})
            if len(result) >= limit:
                break
    return result


@router.get("/applications-by-day")
def get_applications_by_day(
    days: int = 14,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns daily count of jobs applied for the last N days. For chart."""
    from sqlalchemy import func
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(func.date(UserJob.created_at).label("d"), func.count(UserJob.id).label("c"))
        .filter(
            UserJob.user_id == current_user.id,
            UserJob.application_status.in_(APPLIED_STATUSES),
            UserJob.created_at >= cutoff,
        )
        .group_by(func.date(UserJob.created_at))
        .order_by(func.date(UserJob.created_at))
        .all()
    )
    return [{"date": str(row[0]), "count": row[1]} for row in rows]


@router.get("/recent-applications")
def get_recent_applications(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recently submitted jobs (user_jobs with applied status, ordered by created_at desc)."""
    jobs = (
        db.query(UserJob)
        .filter(UserJob.user_id == current_user.id, UserJob.application_status.in_(APPLIED_STATUSES))
        .order_by(UserJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": j.id,
            "title": j.position_title or "Untitled",
            "company": j.company or "",
            "location": j.location or "",
            "application_status": _normalize_status(j.application_status),
            "job_posting_url": j.job_posting_url,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]
