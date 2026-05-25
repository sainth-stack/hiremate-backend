from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, case
from datetime import datetime, timedelta
from typing import List

from backend.app.core.dependencies import get_current_user, get_db, require_ai_token_balance
from backend.jobradar.models.application import (
    Application, StatusHistory, InterviewEvent, HRContact, CompanyProfile
)
from backend.jobradar.services.classifier import classify_jd
from backend.jobradar.services.calendar_service import create_calendar_event, delete_calendar_event
from backend.jobradar.services.salary_service import estimate_salary
from backend.jobradar.services.company_enrichment_service import enrich_company
from backend.jobradar.schemas.application import (
    ApplicationDetailResponse, ApplicationListResponse, 
    HRContactResponse, HRContactCreate, CompanyProfileResponse
)
from backend.app.models.user import User

router = APIRouter()


from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

@router.get("", response_model=List[ApplicationListResponse])
def list_applications(
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List applications with status filtering.
    Optimized for fast loading - defers heavy computations.
    """
    query = db.query(Application).filter(Application.user_id == current_user.id)
    
    if status:
        status_list = [s.strip() for s in status.split(',') if s.strip()]
        query = query.filter(Application.current_status.in_(status_list))
    
    apps = query.order_by(Application.last_activity.desc()).all()
    
    # Use subquery to get counts efficiently
    interview_counts = (
        db.query(
            InterviewEvent.application_id,
            func.count(InterviewEvent.id).label('count'),
            func.min(
                case(
                    (InterviewEvent.scheduled_at > datetime.utcnow(), InterviewEvent.scheduled_at),
                    else_=None
                )
            ).label('next_interview')
        )
        .filter(InterviewEvent.application_id.in_([a.id for a in apps]))
        .group_by(InterviewEvent.application_id)
        .all()
    )
    
    # Build lookup dict
    counts_map = {
        row.application_id: {
            'count': row.count,
            'next_interview': row.next_interview
        }
        for row in interview_counts
    }
    
    # Build response
    results = []
    for app in apps:
        counts = counts_map.get(app.id, {'count': 0, 'next_interview': None})
        app_dict = {
            "id": app.id,
            "company": app.company,
            "role": app.role,
            "platform": app.platform,
            "current_status": app.current_status,
            "applied_date": app.applied_date,
            "last_activity": app.last_activity,
            "next_action": app.next_action,
            "job_url": app.job_url,
            "confidence": app.confidence,
            "low_confidence": app.low_confidence,
            "created_at": app.created_at,
            "interview_events_count": counts['count'],
            "next_interview_at": counts['next_interview'],
        }
        results.append(ApplicationListResponse(**app_dict))
    
    return results


@router.get("/{app_id}", response_model=ApplicationDetailResponse)
def get_application(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single application with full nested details.
    Uses eager loading to avoid N+1 queries.
    """
    # Use eager loading for all relationships
    app = (
        db.query(Application)
        .options(
            selectinload(Application.hr_contacts),
            selectinload(Application.interview_events),
            selectinload(Application.company_profile),
            selectinload(Application.status_history)
        )
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Pydantic will automatically handle the nested relationships
    # because we're using from_attributes=True
    return app


@router.post("")
def create_application(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually add a new application to the tracker."""
    new_app = Application(
        user_id=current_user.id,
        company=payload.get("company"),
        role=payload.get("role") or payload.get("position_title"),
        platform=payload.get("platform") or "Manual",
        current_status=payload.get("current_status") or "applied",
        applied_date=datetime.utcnow(),
        job_url=payload.get("job_url") or payload.get("job_posting_url"),
    )
    db.add(new_app)
    db.flush()
    
    db.add(StatusHistory(
        application_id=new_app.id,
        status=new_app.current_status,
        summary="Application manually added by user",
    ))
    db.commit()
    db.refresh(new_app)
    return _serialize(new_app)


@router.post("/from-jd")
def create_application_from_jd(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Extracts company and role from a JD using AI, then creates an application.
    Also enriches company profile if domain can be extracted.
    Token usage is tracked via real LLM consumption in classify_jd().
    """
    import re
    from urllib.parse import urlparse
    
    jd_text = payload.get("job_description") or payload.get("jd_text", "")
    job_url = payload.get("job_url", "")
    
    if not jd_text.strip() and not job_url.strip():
        raise HTTPException(status_code=400, detail="Job description or URL required")

    # 1. AI Classification
    print(f"Classifying JD with text length: {len(jd_text)}")
    info = classify_jd(jd_text, user_id=current_user.id, email=current_user.email)
    print(f"Classification result: company={info.company if info else None}, role={info.role if info else None}")
    
    company = info.company if info else "Unknown Company"
    role = info.role if info else "Software Engineer"
    
    # 2. Try to extract domain from job_url
    company_profile_id = None
    if job_url:
        try:
            parsed = urlparse(job_url)
            domain = parsed.netloc.replace('www.', '')
            # Skip job boards
            job_boards = ['linkedin.com', 'indeed.com', 'naukri.com', 'monster.com', 'glassdoor.com']
            if domain and not any(board in domain for board in job_boards):
                profile = enrich_company(db, domain, user_id=current_user.id, email=current_user.email)
                company_profile_id = profile.id
        except Exception as e:
            print(f"Failed to enrich company from URL: {e}")
    
    # 3. Create Application
    new_app = Application(
        user_id=current_user.id,
        company=company,
        role=role,
        platform="Manual (AI Extracted)",
        current_status="interview_scheduled",
        applied_date=datetime.utcnow(),
        job_url=job_url,
        company_profile_id=company_profile_id,
    )
    db.add(new_app)
    db.flush()
    
    db.add(StatusHistory(
        application_id=new_app.id,
        status="interview_scheduled",
        summary=f"Prep session created via AI JD Analysis. Extracted: {company} - {role}",
    ))
    db.commit()
    db.refresh(new_app)
    
    return _serialize(new_app)


@router.patch("/{app_id}")
def update_application(
    app_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing application's details or status."""
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    old_status = app.current_status
    
    if "company" in payload: app.company = payload["company"]
    if "role" in payload: app.role = payload["role"]
    if "position_title" in payload: app.role = payload["position_title"]
    if "job_url" in payload: app.job_url = payload["job_url"]
    if "job_posting_url" in payload: app.job_url = payload["job_posting_url"]
    
    if "current_status" in payload and payload["current_status"] != app.current_status:
        app.current_status = payload["current_status"]
        app.last_activity = datetime.utcnow()
        db.add(StatusHistory(
            application_id=app.id,
            status=app.current_status,
            summary=payload.get("status_summary") or "Status manually updated",
        ))
        
        # Trigger calendar sync for interview-related status changes
        if app.current_status in ["interview_scheduled", "in_review"] and old_status != app.current_status:
            background_tasks.add_task(_auto_sync_calendar_events, db, current_user.id, app.id)

    db.commit()
    return _serialize(app)


@router.delete("/{app_id}")
def delete_application(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an application record."""
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    db.delete(app)
    db.commit()
    return {"success": True}


@router.patch("/{app_id}/withdraw")
def withdraw_application(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an application as withdrawn."""
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.current_status = "withdrawn"
    db.add(StatusHistory(
        application_id=app.id,
        status="withdrawn",
        summary="User marked application as withdrawn",
    ))
    db.commit()
    return {"success": True}


@router.post("/{app_id}/hr-contacts", response_model=HRContactResponse)
def create_hr_contact(
    app_id: int,
    contact_data: HRContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually add an HR contact to an application."""
    # Verify application ownership
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Create new contact
    new_contact = HRContact(
        application_id=app_id,
        name=contact_data.name,
        email=contact_data.email,
        title=contact_data.title,
        linkedin_url=contact_data.linkedin_url,
        phone=contact_data.phone,
        created_at=datetime.utcnow()
    )
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    
    return new_contact


@router.delete("/{app_id}/hr-contacts/{contact_id}")
def delete_hr_contact(
    app_id: int,
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an HR contact from an application."""
    # Verify application ownership
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Find and delete contact
    contact = (
        db.query(HRContact)
        .filter(HRContact.id == contact_id, HRContact.application_id == app_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    db.delete(contact)
    db.commit()
    
    return {"success": True, "message": "Contact deleted"}


@router.post("/{app_id}/events/{event_id}/add-to-calendar")
def add_event_to_calendar(
    app_id: int,
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger calendar sync for a specific interview event."""
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    event = (
        db.query(InterviewEvent)
        .filter(InterviewEvent.id == event_id, InterviewEvent.application_id == app_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Interview event not found")
    
    if event.calendar_event_id:
        return {"success": True, "message": "Event already synced to calendar", "calendar_event_id": event.calendar_event_id}
    
    calendar_event_id = create_calendar_event(db, current_user.id, event_id)
    
    if calendar_event_id:
        return {"success": True, "calendar_event_id": calendar_event_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to create calendar event")


@router.delete("/{app_id}/events/{event_id}/remove-from-calendar")
def remove_event_from_calendar(
    app_id: int,
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove calendar event for a specific interview event."""
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    event = (
        db.query(InterviewEvent)
        .filter(InterviewEvent.id == event_id, InterviewEvent.application_id == app_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Interview event not found")
    
    if not event.calendar_event_id:
        return {"success": True, "message": "Event not synced to calendar"}
    
    success = delete_calendar_event(db, current_user.id, event_id)
    
    if success:
        return {"success": True, "message": "Calendar event removed"}
    else:
        raise HTTPException(status_code=500, detail="Failed to remove calendar event")


@router.get("/{app_id}/salary-estimate", dependencies=[Depends(require_ai_token_balance)])
def get_salary_estimate(
    app_id: int,
    refresh: bool = Query(False, description="Force recalculate estimate"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get AI-powered salary estimate for an application.
    Returns cached estimate if available, unless refresh=true.
    """
    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == current_user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Return cached estimate if available and not forcing refresh
    if not refresh and app.salary_estimated_min and app.salary_estimated_max:
        # Infer currency from application or company location
        currency = "INR"  # Default for Indian market
        if app.company_profile and app.company_profile.hq_location:
            location_lower = app.company_profile.hq_location.lower()
            if "india" in location_lower or "bengaluru" in location_lower or "bangalore" in location_lower or "mumbai" in location_lower or "delhi" in location_lower or "hyderabad" in location_lower or "chennai" in location_lower or "pune" in location_lower:
                currency = "INR"
            elif "united states" in location_lower or "usa" in location_lower or "san francisco" in location_lower or "new york" in location_lower or "seattle" in location_lower:
                currency = "USD"
            elif "united kingdom" in location_lower or "uk" in location_lower or "london" in location_lower:
                currency = "GBP"
            elif "europe" in location_lower or "germany" in location_lower or "france" in location_lower or "berlin" in location_lower or "paris" in location_lower:
                currency = "EUR"
        
        return {
            "estimated_min": app.salary_estimated_min,
            "estimated_max": app.salary_estimated_max,
            "currency": currency,
            "confidence": "medium",
            "cached": True,
            "rationale": "Based on previous estimate. Refresh for updated calculation with latest market data.",
            "data_sources_note": "Cached estimate from previous calculation"
        }
    
    # Generate new estimate
    result = estimate_salary(db, current_user.id, app_id)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    result["cached"] = False
    return result


@router.get("/companies/{domain}/profile", response_model=CompanyProfileResponse, dependencies=[Depends(require_ai_token_balance)])
def get_company_profile(
    domain: str,
    refresh: bool = Query(False, description="Force re-enrich the company profile"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get or enrich company profile by domain.
    Use ?refresh=true to force re-enrichment.
    """
    if refresh:
        # Delete existing to force refresh
        existing = db.query(CompanyProfile).filter(CompanyProfile.domain == domain.lower()).first()
        if existing:
            existing.last_enriched_at = datetime.utcnow() - timedelta(days=8)  # Force stale
            db.commit()
    
    profile = enrich_company(db, domain, user_id=current_user.id, email=current_user.email)
    return profile


def _auto_sync_calendar_events(db: Session, user_id: int, app_id: int):
    """Background task: Auto-sync unsynced interview events to calendar."""
    events = (
        db.query(InterviewEvent)
        .filter(
            InterviewEvent.application_id == app_id,
            InterviewEvent.calendar_event_id.is_(None),
            InterviewEvent.scheduled_at.isnot(None),
        )
        .all()
    )
    
    for event in events:
        try:
            create_calendar_event(db, user_id, event.id)
        except Exception as e:
            print(f"Failed to auto-sync event {event.id}: {e}")


def _serialize(app: Application) -> dict:
    return {
        "id": app.id,
        "company": app.company,
        "role": app.role,
        "platform": app.platform,
        "current_status": app.current_status,
        "applied_date": app.applied_date.isoformat() if app.applied_date else None,
        "last_activity": app.last_activity.isoformat() if app.last_activity else None,
        "next_action": app.next_action,
        "job_url": app.job_url,
        "confidence": app.confidence,
        "low_confidence": app.low_confidence,
        "email_thread_id": app.email_thread_id,
        "interview_process": app.interview_process,
        "company_profile_id": app.company_profile_id,
        "salary_min": app.salary_min,
        "salary_max": app.salary_max,
        "salary_currency": app.salary_currency,
        "salary_estimated_min": app.salary_estimated_min,
        "salary_estimated_max": app.salary_estimated_max,
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }
