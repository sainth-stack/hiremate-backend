"""
Google Calendar API service for interview event management.
Automatically syncs interview_events to user's Google Calendar.
"""
from datetime import datetime, timedelta
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from backend.app.services.google_oauth import get_credentials_for_user
from backend.jobradar.models.application import InterviewEvent, Application, HRContact, EventType


def get_calendar_service(creds: Credentials):
    """Build Google Calendar API service."""
    return build("calendar", "v3", credentials=creds)


def create_calendar_event(db: Session, user_id: int, interview_event_id: int) -> Optional[str]:
    """
    Create a Google Calendar event for an interview_event.
    Returns the calendar_event_id or None if failed.
    """
    from backend.app.models.user import User
    
    # Load user and credentials
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.google_access_token:
        return None
    
    try:
        creds = get_credentials_for_user(db, user)
    except Exception:
        return None
    
    # Load interview event with application
    event = (
        db.query(InterviewEvent)
        .filter(InterviewEvent.id == interview_event_id)
        .first()
    )
    if not event:
        return None
    
    application = db.query(Application).filter(Application.id == event.application_id).first()
    if not application:
        return None
    
    # Skip if already synced
    if event.calendar_event_id:
        return event.calendar_event_id
    
    # Build event payload
    event_type_label = _get_event_type_label(event.event_type)
    summary = f"{event_type_label} — {application.company} ({application.role})"
    
    # Build description with HR contacts and notes
    description_parts = [f"**{event.title}**\n"]
    
    if event.notes:
        description_parts.append(f"\n{event.notes}\n")
    
    # Add HR contacts if available
    hr_contacts = (
        db.query(HRContact)
        .filter(HRContact.application_id == application.id)
        .all()
    )
    if hr_contacts:
        description_parts.append("\n**Contacts:**")
        for contact in hr_contacts:
            contact_line = f"- {contact.name}"
            if contact.email:
                contact_line += f" ({contact.email})"
            if contact.title:
                contact_line += f" - {contact.title}"
            description_parts.append(contact_line)
    
    if event.meeting_link:
        description_parts.append(f"\n**Meeting Link:** {event.meeting_link}")
    
    if application.job_url:
        description_parts.append(f"\n**Job Posting:** {application.job_url}")
    
    description = "\n".join(description_parts)
    
    # Calculate start and end times
    if not event.scheduled_at:
        return None
    
    start_time = event.scheduled_at
    duration = event.duration_minutes or 60
    end_time = start_time + timedelta(minutes=duration)
    
    # Location field
    location = event.meeting_link or _format_to_string(event.format)
    
    # Color ID based on event type
    color_id = _get_color_id(event.event_type)
    
    # Build Calendar API payload
    calendar_event = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start_time.isoformat() + "Z",
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end_time.isoformat() + "Z",
            "timeZone": "UTC",
        },
        "location": location,
        "colorId": color_id,
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},  # 24 hours before
                {"method": "popup", "minutes": 30},       # 30 minutes before
            ],
        },
    }
    
    # Create the event
    try:
        service = get_calendar_service(creds)
        created_event = service.events().insert(
            calendarId="primary",
            body=calendar_event,
        ).execute()
        
        calendar_event_id = created_event.get("id")
        
        # Update interview_event with calendar_event_id
        event.calendar_event_id = calendar_event_id
        db.commit()
        
        return calendar_event_id
    except Exception as e:
        print(f"Failed to create calendar event: {e}")
        return None


def update_calendar_event(db: Session, user_id: int, interview_event_id: int) -> bool:
    """
    Update an existing Google Calendar event when interview details change.
    Returns True if successful, False otherwise.
    """
    from backend.app.models.user import User
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.google_access_token:
        return False
    
    try:
        creds = get_credentials_for_user(db, user)
    except Exception:
        return False
    
    event = db.query(InterviewEvent).filter(InterviewEvent.id == interview_event_id).first()
    if not event or not event.calendar_event_id:
        return False
    
    application = db.query(Application).filter(Application.id == event.application_id).first()
    if not application:
        return False
    
    # Build updated payload (same logic as create)
    event_type_label = _get_event_type_label(event.event_type)
    summary = f"{event_type_label} — {application.company} ({application.role})"
    
    description_parts = [f"**{event.title}**\n"]
    if event.notes:
        description_parts.append(f"\n{event.notes}\n")
    
    hr_contacts = (
        db.query(HRContact)
        .filter(HRContact.application_id == application.id)
        .all()
    )
    if hr_contacts:
        description_parts.append("\n**Contacts:**")
        for contact in hr_contacts:
            contact_line = f"- {contact.name}"
            if contact.email:
                contact_line += f" ({contact.email})"
            if contact.title:
                contact_line += f" - {contact.title}"
            description_parts.append(contact_line)
    
    if event.meeting_link:
        description_parts.append(f"\n**Meeting Link:** {event.meeting_link}")
    
    if application.job_url:
        description_parts.append(f"\n**Job Posting:** {application.job_url}")
    
    description = "\n".join(description_parts)
    
    if not event.scheduled_at:
        return False
    
    start_time = event.scheduled_at
    duration = event.duration_minutes or 60
    end_time = start_time + timedelta(minutes=duration)
    
    location = event.meeting_link or _format_to_string(event.format)
    color_id = _get_color_id(event.event_type)
    
    calendar_event = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start_time.isoformat() + "Z",
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end_time.isoformat() + "Z",
            "timeZone": "UTC",
        },
        "location": location,
        "colorId": color_id,
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 30},
            ],
        },
    }
    
    try:
        service = get_calendar_service(creds)
        service.events().update(
            calendarId="primary",
            eventId=event.calendar_event_id,
            body=calendar_event,
        ).execute()
        return True
    except Exception as e:
        print(f"Failed to update calendar event: {e}")
        return False


def delete_calendar_event(db: Session, user_id: int, interview_event_id: int) -> bool:
    """
    Delete a Google Calendar event (e.g., when application is withdrawn/rejected).
    Returns True if successful, False otherwise.
    """
    from backend.app.models.user import User
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.google_access_token:
        return False
    
    try:
        creds = get_credentials_for_user(db, user)
    except Exception:
        return False
    
    event = db.query(InterviewEvent).filter(InterviewEvent.id == interview_event_id).first()
    if not event or not event.calendar_event_id:
        return False
    
    try:
        service = get_calendar_service(creds)
        service.events().delete(
            calendarId="primary",
            eventId=event.calendar_event_id,
        ).execute()
        
        # Clear the calendar_event_id
        event.calendar_event_id = None
        db.commit()
        
        return True
    except Exception as e:
        print(f"Failed to delete calendar event: {e}")
        return False


def _get_event_type_label(event_type: EventType) -> str:
    """Convert EventType enum to human-readable label."""
    if not event_type:
        return "Interview"
    
    labels = {
        EventType.interview: "Interview",
        EventType.assessment: "Assessment",
        EventType.technical_screen: "Technical Screen",
        EventType.culture_fit: "Culture Fit Interview",
        EventType.offer_call: "Offer Call",
        EventType.onboarding: "Onboarding",
    }
    return labels.get(event_type, "Interview")


def _format_to_string(format_enum) -> str:
    """Convert MeetingFormat enum to string."""
    if not format_enum:
        return "TBD"
    
    format_map = {
        "video": "Video Call",
        "phone": "Phone Call",
        "onsite": "On-site",
        "async_format": "Asynchronous",
    }
    return format_map.get(format_enum.value if hasattr(format_enum, 'value') else str(format_enum), "TBD")


def _get_color_id(event_type: EventType) -> str:
    """
    Get Google Calendar color ID based on event type.
    Color IDs: https://developers.google.com/calendar/api/v3/reference/colors
    5 = banana/yellow (assessments)
    9 = blueberry/blue (interviews)
    2 = sage/green (offer calls)
    11 = tomato/red (technical screens)
    """
    if not event_type:
        return "9"
    
    color_map = {
        EventType.assessment: "5",          # yellow for take-home assignments
        EventType.interview: "9",           # blue for general interviews
        EventType.technical_screen: "11",   # red for technical interviews
        EventType.culture_fit: "9",         # blue for behavioral
        EventType.offer_call: "2",          # green for offers
        EventType.onboarding: "2",          # green for onboarding
    }
    return color_map.get(event_type, "9")
