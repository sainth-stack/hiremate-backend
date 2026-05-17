"""
Admin API - platform-wide analytics, users, companies, learning, extension health.
All routes require get_admin_user (is_admin=True).
"""
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from backend.app.core.dependencies import get_admin_user, get_db
from backend.app.models.user import User
from backend.app.models.profile import Profile
from backend.app.models.user_job import UserJob
from backend.app.models.user_resume import UserResume
from backend.app.models.career_page_visit import CareerPageVisit
from backend.app.models.form_field_learning import (
    SharedFormStructure,
    UserFieldAnswer,
    UserSubmissionHistory,
)
from backend.app.models.token_usage import TokenUsage
from backend.app.models.scraper_run import ScraperRun

router = APIRouter(prefix="/admin", tags=["admin"])

APPLIED_STATUSES = frozenset({
    "applied", "interview", "closed",
    "Applied", "Interviewing", "Offer", "Rejected", "Withdrawn",
})


def _parse_date(d: str | None) -> datetime | None:
    """Parse YYYY-MM-DD string to datetime at midnight UTC."""
    if not d:
        return None
    try:
        return datetime.strptime(d.strip()[:10], "%Y-%m-%d")
    except ValueError:
        return None


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


# --- Overview ---


@router.get("/overview")
def get_admin_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """
    Platform-wide stats: total users, active users (7/30 days), career visits, autofill uses,
    jobs saved/applied, form submissions, new users by day (last 30 days).
    """
    now = datetime.utcnow()
    cutoff_7 = now - timedelta(days=7)
    cutoff_30 = now - timedelta(days=30)

    total_users = db.query(User).filter(User.is_active == 1).count()

    active_users_7_ids = set()
    for row in db.query(CareerPageVisit.user_id).filter(CareerPageVisit.created_at >= cutoff_7).distinct().all():
        active_users_7_ids.add(row[0])
    for row in db.query(UserJob.user_id).filter(UserJob.updated_at >= cutoff_7).all():
        active_users_7_ids.add(row[0])
    active_users_7 = len(active_users_7_ids)

    active_users_30_ids = set()
    for row in db.query(CareerPageVisit.user_id).filter(CareerPageVisit.created_at >= cutoff_30).distinct().all():
        active_users_30_ids.add(row[0])
    for row in db.query(UserJob.user_id).filter(UserJob.updated_at >= cutoff_30).all():
        active_users_30_ids.add(row[0])
    active_users_30 = len(active_users_30_ids)

    career_visits = db.query(CareerPageVisit).filter(CareerPageVisit.action_type == "page_view").count()
    autofill_uses = db.query(CareerPageVisit).filter(CareerPageVisit.action_type == "autofill_used").count()

    jobs_saved = db.query(UserJob).filter(
        or_(
            UserJob.application_status == "saved",
            UserJob.application_status.is_(None),
            UserJob.application_status == "",
        )
    ).count()
    jobs_applied = db.query(UserJob).filter(UserJob.application_status.in_(APPLIED_STATUSES)).count()

    form_submissions = db.query(UserSubmissionHistory).count()

    new_users_by_day = (
        db.query(func.date(User.created_at).label("d"), func.count(User.id).label("c"))
        .filter(User.created_at >= cutoff_30)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
        .all()
    )
    new_users_by_day = [{"date": str(row[0]), "count": row[1]} for row in new_users_by_day]

    return {
        "stats": {
            "total_users": total_users,
            "active_users_7d": active_users_7,
            "active_users_30d": active_users_30,
            "career_page_visits": career_visits,
            "autofill_uses": autofill_uses,
            "jobs_saved": jobs_saved,
            "jobs_applied": jobs_applied,
            "form_submissions": form_submissions,
        },
        "new_users_by_day": new_users_by_day,
    }


# --- Users ---


@router.get("/users")
def get_admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Paginated users list with jobs_count, career_visits_count, last_activity_at."""
    q = db.query(User).filter(User.is_active == 1)
    if search and search.strip():
        s = f"%{search.strip()}%"
        q = q.filter(
            or_(
                User.email.ilike(s),
                User.first_name.ilike(s),
                User.last_name.ilike(s),
            )
        )
    total = q.count()
    offset = (page - 1) * limit
    users = q.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    user_ids = [u.id for u in users]

    jobs_by_user = {}
    if user_ids:
        for row in db.query(UserJob.user_id, func.count(UserJob.id)).filter(
            UserJob.user_id.in_(user_ids)
        ).group_by(UserJob.user_id).all():
            jobs_by_user[row[0]] = row[1]
    visits_by_user = {}
    if user_ids:
        for row in db.query(CareerPageVisit.user_id, func.count(CareerPageVisit.id)).filter(
            CareerPageVisit.user_id.in_(user_ids)
        ).group_by(CareerPageVisit.user_id).all():
            visits_by_user[row[0]] = row[1]
    last_visit_by_user = {}
    if user_ids:
        for row in db.query(CareerPageVisit.user_id, func.max(CareerPageVisit.created_at)).filter(
            CareerPageVisit.user_id.in_(user_ids)
        ).group_by(CareerPageVisit.user_id).all():
            last_visit_by_user[row[0]] = row[1]
    last_job_by_user = {}
    if user_ids:
        for row in db.query(UserJob.user_id, func.max(UserJob.updated_at)).filter(
            UserJob.user_id.in_(user_ids)
        ).group_by(UserJob.user_id).all():
            last_job_by_user[row[0]] = row[1]

    result = []
    for u in users:
        jobs_count = jobs_by_user.get(u.id, 0)
        visits_count = visits_by_user.get(u.id, 0)
        last_visit = last_visit_by_user.get(u.id)
        last_job = last_job_by_user.get(u.id)
        last_activity = None
        if last_visit and last_job:
            last_activity = max(last_visit, last_job)
        elif last_visit:
            last_activity = last_visit
        elif last_job:
            last_activity = last_job

        result.append({
            "id": u.id,
            "email": u.email or "",
            "first_name": u.first_name or "",
            "last_name": u.last_name or "",
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_activity_at": last_activity.isoformat() if last_activity else None,
            "jobs_count": jobs_count,
            "career_visits_count": visits_count,
        })
    return {"users": result, "total": total, "page": page, "limit": limit}


@router.get("/users/{user_id}/usage")
def get_admin_user_usage(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Detailed usage for a single user: jobs breakdown, visits by action_type, field answers, submissions, resumes."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    jobs_saved = db.query(UserJob).filter(
        UserJob.user_id == user_id,
        or_(
            UserJob.application_status == "saved",
            UserJob.application_status.is_(None),
            UserJob.application_status == "",
        )
    ).count()
    jobs_applied = db.query(UserJob).filter(
        UserJob.user_id == user_id,
        UserJob.application_status.in_(APPLIED_STATUSES),
    ).count()

    visits_by_type = (
        db.query(CareerPageVisit.action_type, func.count(CareerPageVisit.id))
        .filter(CareerPageVisit.user_id == user_id)
        .group_by(CareerPageVisit.action_type)
        .all()
    )
    career_page_visits = {row[0]: row[1] for row in visits_by_type}

    user_field_answers_count = db.query(UserFieldAnswer).filter(UserFieldAnswer.user_id == user_id).count()
    user_submission_history_count = db.query(UserSubmissionHistory).filter(
        UserSubmissionHistory.user_id == user_id
    ).count()
    resumes_count = db.query(UserResume).filter(UserResume.user_id == user_id).count()
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile and profile.resume_url:
        resumes_count = max(resumes_count, 1)

    return {
        "user_id": user_id,
        "email": user.email or "",
        "jobs": {"saved": jobs_saved, "applied": jobs_applied},
        "career_page_visits": career_page_visits,
        "user_field_answers_count": user_field_answers_count,
        "user_submission_history_count": user_submission_history_count,
        "resumes_count": resumes_count,
    }


# --- Companies viewed ---


@router.get("/companies-viewed")
def get_admin_companies_viewed(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Companies aggregated from CareerPageVisit + UserJob.company: unique_users, total_visits, autofill_uses, last_visited."""
    cutoff_start = _parse_date(from_date) if from_date else None
    cutoff_end = _parse_date(to_date) if to_date else None
    if cutoff_end:
        cutoff_end = datetime(cutoff_end.year, cutoff_end.month, cutoff_end.day, 23, 59, 59)

    visit_q = db.query(
        CareerPageVisit.company_name,
        CareerPageVisit.page_url,
        CareerPageVisit.action_type,
        CareerPageVisit.created_at,
        CareerPageVisit.user_id,
    ).filter(CareerPageVisit.company_name.isnot(None), CareerPageVisit.company_name != "")
    if cutoff_start:
        visit_q = visit_q.filter(CareerPageVisit.created_at >= cutoff_start)
    if cutoff_end:
        visit_q = visit_q.filter(CareerPageVisit.created_at <= cutoff_end)
    visits = visit_q.all()

    job_q = db.query(UserJob.company).filter(UserJob.company.isnot(None), UserJob.company != "").distinct()
    if cutoff_start:
        job_q = job_q.filter(UserJob.created_at >= cutoff_start)
    if cutoff_end:
        job_q = job_q.filter(UserJob.created_at <= cutoff_end)
    job_companies = {str(r[0]).strip().lower() for r in job_q.all() if r[0]}

    agg = {}
    for r in visits:
        name = (r.company_name or "").strip()
        if not name:
            name = _derive_company_from_url(r.page_url)
        if not name:
            continue
        key = name.lower()
        if key not in agg:
            agg[key] = {
                "company_name": name,
                "unique_users": set(),
                "total_visits": 0,
                "autofill_uses": 0,
                "last_visited_at": None,
            }
        agg[key]["unique_users"].add(r.user_id)
        agg[key]["total_visits"] += 1
        if r.action_type == "autofill_used":
            agg[key]["autofill_uses"] += 1
        if r.created_at and (
            agg[key]["last_visited_at"] is None or r.created_at > agg[key]["last_visited_at"]
        ):
            agg[key]["last_visited_at"] = r.created_at

    for c in job_companies:
        if c not in agg:
            agg[c] = {
                "company_name": c.title(),
                "unique_users": set(),
                "total_visits": 0,
                "autofill_uses": 0,
                "last_visited_at": None,
            }

    result = []
    for v in agg.values():
        result.append({
            "company_name": v["company_name"],
            "unique_users": len(v["unique_users"]),
            "total_visits": v["total_visits"],
            "autofill_uses": v["autofill_uses"],
            "last_visited_at": v["last_visited_at"].isoformat() if v["last_visited_at"] else None,
        })
    result.sort(key=lambda x: (x["last_visited_at"] or ""), reverse=True)
    total = len(result)
    offset = (page - 1) * limit
    result = result[offset : offset + limit]
    return {"companies": result, "total": total, "page": page, "limit": limit}


# --- Career page links ---


@router.get("/career-page-links")
def get_admin_career_page_links(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Top career page URLs with visit_count, autofill_count, unique_users."""
    cutoff_start = _parse_date(from_date) if from_date else None
    cutoff_end = _parse_date(to_date) if to_date else None
    if cutoff_end:
        cutoff_end = datetime(cutoff_end.year, cutoff_end.month, cutoff_end.day, 23, 59, 59)

    q = db.query(
        CareerPageVisit.page_url,
        CareerPageVisit.action_type,
        CareerPageVisit.user_id,
    )
    if cutoff_start:
        q = q.filter(CareerPageVisit.created_at >= cutoff_start)
    if cutoff_end:
        q = q.filter(CareerPageVisit.created_at <= cutoff_end)
    rows = q.all()

    agg = {}
    for r in rows:
        url = (r.page_url or "").strip() or "Unknown"
        if url not in agg:
            agg[url] = {"visit_count": 0, "autofill_count": 0, "unique_users": set()}
        agg[url]["visit_count"] += 1
        if r.action_type == "autofill_used":
            agg[url]["autofill_count"] += 1
        agg[url]["unique_users"].add(r.user_id)

    result = [
        {
            "page_url": k,
            "visit_count": v["visit_count"],
            "autofill_count": v["autofill_count"],
            "unique_users": len(v["unique_users"]),
        }
        for k, v in agg.items()
    ]
    result.sort(key=lambda x: x["visit_count"], reverse=True)
    total = len(result)
    offset = (page - 1) * limit
    result = result[offset : offset + limit]
    return {"links": result, "total": total, "page": page, "limit": limit}


# --- Learning / form-field training ---


@router.get("/learning/form-structures")
def get_admin_learning_form_structures(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """SharedFormStructure stats: count by domain, top domains by sample_count, ATS platforms."""
    total = db.query(SharedFormStructure).count()
    by_domain = (
        db.query(SharedFormStructure.domain, func.count(SharedFormStructure.id), func.sum(SharedFormStructure.sample_count))
        .group_by(SharedFormStructure.domain)
        .all()
    )
    domains = [{"domain": r[0], "count": r[1], "sample_count": r[2] or 0} for r in by_domain]
    domains.sort(key=lambda x: x["sample_count"], reverse=True)
    top_domains = domains[:20]

    ats_platforms = (
        db.query(SharedFormStructure.ats_platform, func.count(SharedFormStructure.id))
        .filter(SharedFormStructure.ats_platform.isnot(None), SharedFormStructure.ats_platform != "")
        .group_by(SharedFormStructure.ats_platform)
        .all()
    )
    return {
        "total": total,
        "top_domains": top_domains,
        "ats_platforms": [{"ats_platform": r[0], "count": r[1]} for r in ats_platforms],
    }


@router.get("/learning/user-answers")
def get_admin_learning_user_answers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """UserFieldAnswer stats: total, by user (top by used_count), by source."""
    total = db.query(UserFieldAnswer).count()
    by_user = (
        db.query(UserFieldAnswer.user_id, func.count(UserFieldAnswer.id).label("c"), func.sum(UserFieldAnswer.used_count))
        .group_by(UserFieldAnswer.user_id)
        .order_by(func.sum(UserFieldAnswer.used_count).desc())
        .limit(20)
        .all()
    )
    top_users = [{"user_id": r[0], "answers_count": r[1], "total_used_count": r[2] or 0} for r in by_user]
    by_source = (
        db.query(UserFieldAnswer.source, func.count(UserFieldAnswer.id))
        .group_by(UserFieldAnswer.source)
        .all()
    )
    return {
        "total": total,
        "top_users": top_users,
        "by_source": [{"source": r[0] or "unknown", "count": r[1]} for r in by_source],
    }


@router.get("/learning/submissions")
def get_admin_learning_submissions(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """UserSubmissionHistory stats: by day, by domain, by user."""
    cutoff_start = _parse_date(from_date) if from_date else None
    cutoff_end = _parse_date(to_date) if to_date else None
    if cutoff_end:
        cutoff_end = datetime(cutoff_end.year, cutoff_end.month, cutoff_end.day, 23, 59, 59)

    q = db.query(UserSubmissionHistory)
    if cutoff_start:
        q = q.filter(UserSubmissionHistory.submitted_at >= cutoff_start)
    if cutoff_end:
        q = q.filter(UserSubmissionHistory.submitted_at <= cutoff_end)

    total = q.count()
    by_day = (
        db.query(func.date(UserSubmissionHistory.submitted_at).label("d"), func.count(UserSubmissionHistory.id))
        .filter(UserSubmissionHistory.submitted_at.isnot(None))
    )
    if cutoff_start:
        by_day = by_day.filter(UserSubmissionHistory.submitted_at >= cutoff_start)
    if cutoff_end:
        by_day = by_day.filter(UserSubmissionHistory.submitted_at <= cutoff_end)
    by_day = by_day.group_by(func.date(UserSubmissionHistory.submitted_at)).order_by(
        func.date(UserSubmissionHistory.submitted_at)
    ).all()
    by_domain = (
        db.query(UserSubmissionHistory.domain, func.count(UserSubmissionHistory.id))
        .filter(UserSubmissionHistory.domain.isnot(None), UserSubmissionHistory.domain != "")
    )
    if cutoff_start:
        by_domain = by_domain.filter(UserSubmissionHistory.submitted_at >= cutoff_start)
    if cutoff_end:
        by_domain = by_domain.filter(UserSubmissionHistory.submitted_at <= cutoff_end)
    by_domain = by_domain.group_by(UserSubmissionHistory.domain).order_by(
        func.count(UserSubmissionHistory.id).desc()
    ).limit(20).all()
    by_user = (
        db.query(UserSubmissionHistory.user_id, func.count(UserSubmissionHistory.id))
    )
    if cutoff_start:
        by_user = by_user.filter(UserSubmissionHistory.submitted_at >= cutoff_start)
    if cutoff_end:
        by_user = by_user.filter(UserSubmissionHistory.submitted_at <= cutoff_end)
    by_user = by_user.group_by(UserSubmissionHistory.user_id).order_by(
        func.count(UserSubmissionHistory.id).desc()
    ).limit(20).all()

    return {
        "total": total,
        "by_day": [{"date": str(r[0]), "count": r[1]} for r in by_day],
        "by_domain": [{"domain": r[0] or "unknown", "count": r[1]} for r in by_domain],
        "top_users": [{"user_id": r[0], "count": r[1]} for r in by_user],
    }


# --- Submission Logs (individual detail) ---


@router.get("/learning/submission-logs")
def get_admin_submission_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    user_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Paginated individual submissions with mapping analysis summary."""
    cutoff_start = _parse_date(from_date) if from_date else None
    cutoff_end = _parse_date(to_date) if to_date else None
    if cutoff_end:
        cutoff_end = datetime(cutoff_end.year, cutoff_end.month, cutoff_end.day, 23, 59, 59)

    q = db.query(UserSubmissionHistory)
    if cutoff_start:
        q = q.filter(UserSubmissionHistory.submitted_at >= cutoff_start)
    if cutoff_end:
        q = q.filter(UserSubmissionHistory.submitted_at <= cutoff_end)
    if user_id is not None:
        q = q.filter(UserSubmissionHistory.user_id == user_id)

    total = q.count()
    offset = (page - 1) * limit
    rows = q.order_by(UserSubmissionHistory.submitted_at.desc()).offset(offset).limit(limit).all()

    # Batch-fetch user emails
    user_ids = list({r.user_id for r in rows})
    email_map = {}
    if user_ids:
        for u in db.query(User.id, User.email).filter(User.id.in_(user_ids)).all():
            email_map[u.id] = u.email or ""

    result = []
    for r in rows:
        analysis = r.mapping_analysis or {}
        result.append({
            "id": r.id,
            "user_id": r.user_id,
            "email": email_map.get(r.user_id, ""),
            "domain": r.domain or "",
            "url": r.url or "",
            "ats_platform": r.ats_platform or "unknown",
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "field_count": r.field_count or 0,
            "filled_count": r.filled_count or 0,
            "correctly_mapped": analysis.get("correctly_mapped", 0),
            "user_changed": analysis.get("user_changed", 0),
            "unmapped": analysis.get("unmapped", 0),
            "accuracy_pct": analysis.get("accuracy_pct", 0),
        })
    return {"submissions": result, "total": total, "page": page, "limit": limit}


@router.get("/learning/submission-logs/{submission_id}")
def get_admin_submission_log_detail(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Single submission detail with full field-level mapping data."""
    row = db.query(UserSubmissionHistory).filter(UserSubmissionHistory.id == submission_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")

    user = db.query(User).filter(User.id == row.user_id).first()
    email = user.email if user else ""

    return {
        "id": row.id,
        "user_id": row.user_id,
        "email": email,
        "domain": row.domain or "",
        "url": row.url or "",
        "ats_platform": row.ats_platform or "unknown",
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "field_count": row.field_count or 0,
        "filled_count": row.filled_count or 0,
        "submitted_fields": row.submitted_fields or [],
        "mapping_analysis": row.mapping_analysis or {},
        "unfilled_profile_keys": row.unfilled_profile_keys or [],
    }


# --- Extension health (placeholder) ---


@router.get("/extension/errors")
def get_admin_extension_errors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Extension error reporting - placeholder (extension errors not stored in DB yet)."""
    return {"errors": [], "message": "Extension errors are not persisted in DB yet. Placeholder for future."}


# --- Ingestion Analytics ---


def _normalize_portal_breakdown(detail_json: dict | None) -> list[dict]:
    detail = detail_json or {}
    pb = detail.get("portal_breakdown")
    if isinstance(pb, list):
        out = []
        for row in pb:
            if not isinstance(row, dict):
                continue
            out.append({
                "portal": str(row.get("portal") or "unknown"),
                "fetched_jobs": int(row.get("fetched_jobs") or 0),
            })
        return out

    # Backward-compatible fallback used by unified ingest detail payload.
    by_source = detail.get("unified_sources_seen")
    if isinstance(by_source, dict):
        return [
            {"portal": str(k), "fetched_jobs": int(v or 0)}
            for k, v in by_source.items()
            if k
        ]
    return []


@router.get("/ingestion-runs")
def get_admin_ingestion_runs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    source: str | None = Query(None),
    success: bool | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Paginated ingestion run analytics with per-portal fetched-job counts."""
    cutoff_start = _parse_date(from_date) if from_date else None
    cutoff_end = _parse_date(to_date) if to_date else None
    if cutoff_end:
        cutoff_end = datetime(cutoff_end.year, cutoff_end.month, cutoff_end.day, 23, 59, 59)

    def _apply_filters(q):
        if source and source.strip():
            q = q.filter(ScraperRun.source == source.strip())
        if success is not None:
            q = q.filter(ScraperRun.success == success)
        if cutoff_start:
            q = q.filter(ScraperRun.started_at >= cutoff_start)
        if cutoff_end:
            q = q.filter(ScraperRun.started_at <= cutoff_end)
        return q

    q = _apply_filters(db.query(ScraperRun))
    total = q.count()
    rows = (
        q.order_by(ScraperRun.started_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    summary = _apply_filters(
        db.query(
            func.count(ScraperRun.id),
            func.sum(ScraperRun.total_jobs_seen),
            func.sum(ScraperRun.inserted),
            func.sum(ScraperRun.updated),
            func.sum(ScraperRun.skipped),
            func.sum(ScraperRun.errors),
        )
    ).first()

    items = []
    for r in rows:
        duration_seconds = None
        if r.started_at and r.ended_at:
            duration_seconds = max(0, int((r.ended_at - r.started_at).total_seconds()))
        items.append({
            "id": r.id,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
            "duration_seconds": duration_seconds,
            "source": r.source,
            "success": bool(r.success),
            "dry_run": bool(r.dry_run),
            "inserted": int(r.inserted or 0),
            "updated": int(r.updated or 0),
            "skipped": int(r.skipped or 0),
            "filtered_out": int(r.filtered_out or 0),
            "errors": int(r.errors or 0),
            "total_jobs_seen": int(r.total_jobs_seen or 0),
            "total_tokens": int(r.total_tokens or 0),
            "total_cost": float(r.total_cost or 0.0),
            "error_summary": r.error_summary,
            "portal_breakdown": _normalize_portal_breakdown(r.detail_json),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "summary": {
            "runs": int((summary[0] if summary else 0) or 0),
            "total_jobs_seen": int((summary[1] if summary else 0) or 0),
            "inserted": int((summary[2] if summary else 0) or 0),
            "updated": int((summary[3] if summary else 0) or 0),
            "skipped": int((summary[4] if summary else 0) or 0),
            "errors": int((summary[5] if summary else 0) or 0),
        },
    }

@router.get("/token-usage")
def get_admin_token_usage(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    email: str | None = Query(None),
    model: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """
    Detailed AI token usage logs and aggregation for the Admin Dashboard.
    Supports filtering by from_date, to_date, email (search), and model.
    """
    # 1. Date Parsing
    cutoff_start = _parse_date(from_date) if from_date else None
    cutoff_end = _parse_date(to_date) if to_date else None
    if cutoff_end:
        # Include the entire end day
        cutoff_end = datetime(cutoff_end.year, cutoff_end.month, cutoff_end.day, 23, 59, 59)

    # 2. Base Filter Application
    def apply_advanced_filters(query, model_attr=TokenUsage.created_at):
        if cutoff_start:
            query = query.filter(TokenUsage.created_at >= cutoff_start)
        if cutoff_end:
            query = query.filter(TokenUsage.created_at <= cutoff_end)
        if email:
            query = query.filter(TokenUsage.email.ilike(f"%{email}%"))
        if model and model != "All Models":
            query = query.filter(TokenUsage.model == model)
        return query

    # 3. Aggregates
    summary_q = db.query(func.sum(TokenUsage.cost), func.sum(TokenUsage.total_tokens))
    summary_q = apply_advanced_filters(summary_q)
    
    summary_res = summary_q.one()
    total_cost = summary_res[0] or 0.0
    total_tokens = summary_res[1] or 0
    
    # 4. Daily cost aggregation
    daily_cutoff_start = cutoff_start or (datetime.utcnow() - timedelta(days=30))
    daily_stats_q = db.query(
        func.date(TokenUsage.created_at).label("d"),
        func.sum(TokenUsage.cost).label("c"),
        func.sum(TokenUsage.total_tokens).label("t")
    ).filter(TokenUsage.created_at >= daily_cutoff_start)
    
    if cutoff_end:
        daily_stats_q = daily_stats_q.filter(TokenUsage.created_at <= cutoff_end)
    if email:
        daily_stats_q = daily_stats_q.filter(TokenUsage.email.ilike(f"%{email}%"))
    if model and model != "All Models":
        daily_stats_q = daily_stats_q.filter(TokenUsage.model == model)
        
    daily_stats = (
        daily_stats_q
        .group_by(func.date(TokenUsage.created_at))
        .order_by(func.date(TokenUsage.created_at))
        .all()
    )
    chart_data = [{"date": str(row[0]), "cost": row[1], "tokens": row[2]} for row in daily_stats]

    # 5. Model breakdown
    model_stats_q = db.query(
        TokenUsage.model,
        func.sum(TokenUsage.cost).label("c"),
        func.sum(TokenUsage.total_tokens).label("t"),
        func.count(TokenUsage.id).label("n")
    )
    model_stats_q = apply_advanced_filters(model_stats_q)
    model_stats = model_stats_q.group_by(TokenUsage.model).all()
    models = [{"model": r[0], "cost": r[1], "tokens": r[2], "calls": r[3]} for r in model_stats]

    # 6. Provider breakdown
    provider_stats_q = db.query(
        TokenUsage.provider,
        func.sum(TokenUsage.cost).label("c"),
        func.sum(TokenUsage.total_tokens).label("t"),
        func.count(TokenUsage.id).label("n")
    )
    provider_stats_q = apply_advanced_filters(provider_stats_q)
    provider_stats = provider_stats_q.group_by(TokenUsage.provider).all()
    providers = [{"provider": r[0], "cost": float(r[1]), "tokens": r[2], "calls": r[3]} for r in provider_stats]

    # 7. Paginated logs
    q = apply_advanced_filters(db.query(TokenUsage))
    total = q.count()
    offset = (page - 1) * limit
    logs = q.order_by(TokenUsage.created_at.desc()).offset(offset).limit(limit).all()


    log_data = []
    for l in logs:
        log_data.append({
            "id": l.id,
            "user_id": l.user_id,
            "email": l.email,
            "model": l.model,
            "provider": l.provider,
            "prompt_tokens": l.prompt_tokens,
            "completion_tokens": l.completion_tokens,
            "total_tokens": l.total_tokens,
            "cost": float(l.cost),
            "feature": l.feature,
            "timestamp": l.created_at.isoformat()
        })

    return {
        "summary": {
            "total_cost": float(total_cost),
            "total_tokens": int(total_tokens),
            "records": total
        },
        "chart_data": chart_data,
        "models": models,
        "providers": providers,
        "logs": log_data,
        "total": total,
        "page": page,
        "limit": limit
    }

