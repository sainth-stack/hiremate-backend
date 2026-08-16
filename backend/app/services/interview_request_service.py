"""Shared helpers for interview requests and launches."""
from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.models.interview import Interview
from backend.app.models.interview_request import InterviewRequest
from backend.app.models.launched_interview import LaunchedInterview, LaunchedInterviewUser
from backend.app.models.user import User
from backend.app.services.interview_assignment import (
    build_relative_interview_url,
    normalize_assignment_status,
)
from backend.app.services.interview_access import create_interview_access_token
from backend.app.services.interview_email_service import (
    build_interview_link,
    send_interview_completion_emails,
    send_interview_invitation_email,
    send_new_interview_request_admin_email,
)
from backend.app.services.interview_summary import resolve_interview_summary
from backend.app.services.voice.voice_config import default_launch_voice


def mark_request_in_progress(db: Session, user_id: int, interview_id: int) -> None:
    request = (
        db.query(InterviewRequest)
        .filter(
            InterviewRequest.user_id == user_id,
            InterviewRequest.interview_id == interview_id,
            InterviewRequest.status.in_(["pending", "requested"]),
        )
        .order_by(InterviewRequest.created_at.desc())
        .first()
    )
    if request and request.status == "pending":
        request.status = "in_progress"

    assignment = (
        db.query(LaunchedInterviewUser)
        .join(LaunchedInterview, LaunchedInterviewUser.launched_interview_id == LaunchedInterview.id)
        .filter(
            LaunchedInterviewUser.user_id == user_id,
            LaunchedInterview.interview_id == interview_id,
        )
        .order_by(LaunchedInterview.launched_at.desc())
        .first()
    )
    if assignment and assignment.status == "pending":
        assignment.status = "in_progress"

    db.commit()


def mark_request_completed(
    db: Session,
    *,
    user_id: int,
    interview_id: int,
    score: int,
    user_email: str,
    user_name: str | None = None,
    interview_title: str | None = None,
) -> None:
    request = (
        db.query(InterviewRequest)
        .filter(
            InterviewRequest.user_id == user_id,
            InterviewRequest.interview_id == interview_id,
            InterviewRequest.status.in_(["pending", "in_progress"]),
        )
        .order_by(InterviewRequest.created_at.desc())
        .first()
    )
    if not request:
        return

    request.status = "completed"
    request.score = score
    request.completed_at = datetime.utcnow()
    db.commit()

    send_interview_completion_emails(
        user_email=user_email,
        user_name=user_name,
        interview_title=interview_title or request.domain,
        score=score,
        domain=request.domain,
    )


def launch_interview_for_user(
    db: Session,
    *,
    interview: Interview,
    user: User,
    title: str,
    difficulty: str,
    description: str,
    launched_by_user_id: int | None,
    interview_created_at: datetime | None = None,
) -> tuple[LaunchedInterview, LaunchedInterviewUser]:
    default_voice = default_launch_voice()
    launch = LaunchedInterview(
        interview_id=interview.id,
        title=title.strip(),
        difficulty=difficulty,
        description=description,
        summary=resolve_interview_summary(
            title=interview.title,
            description=interview.description,
            difficulty=interview.difficulty,
            summary=interview.summary,
        ),
        interview_created_at=interview_created_at or interview.created_at,
        launched_by_user_id=launched_by_user_id,
        voice_provider=default_voice.provider,
        voice_id=default_voice.voice_id,
        voice_label=default_voice.voice_label,
        tts_language_code=default_voice.language_code,
        question_count=interview.question_count or 15,
    )
    db.add(launch)
    db.flush()

    assignment = LaunchedInterviewUser(
        launched_interview_id=launch.id,
        user_id=user.id,
        user_email=user.email,
        status="pending",
    )
    db.add(assignment)
    db.flush()
    return launch, assignment


def launch_from_interview_request(
    db: Session,
    *,
    request: InterviewRequest,
    interview: Interview,
    title: str,
    difficulty: str,
    description: str,
    admin_user_id: int,
) -> tuple[LaunchedInterview, LaunchedInterviewUser, str]:
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise ValueError("Request user not found")

    launch, assignment = launch_interview_for_user(
        db,
        interview=interview,
        user=user,
        title=title,
        difficulty=difficulty,
        description=description,
        launched_by_user_id=admin_user_id,
        interview_created_at=interview.created_at,
    )

    request.status = "pending"
    request.interview_id = interview.id
    request.launched_interview_user_id = assignment.id
    request.launched_at = datetime.utcnow()

    db.commit()
    db.refresh(request)
    db.refresh(assignment)

    display_name = f"{user.first_name} {user.last_name}".strip() or user.email
    access_token = create_interview_access_token(
        user_id=user.id,
        interview_id=interview.id,
        assignment_id=assignment.id,
    )
    send_interview_invitation_email(
        to_email=user.email,
        user_id=user.id,
        interview_id=interview.id,
        title=title,
        difficulty=difficulty,
        summary=resolve_interview_summary(
            title=interview.title,
            description=interview.description,
            difficulty=interview.difficulty,
            summary=interview.summary,
        ),
        user_name=display_name,
        access_token=access_token,
    )

    interview_url = build_interview_link(user.id, interview.id, access_token)
    return launch, assignment, interview_url


def _score_from_assignment(assignment: LaunchedInterviewUser) -> int | None:
    data = assignment.submission_data or {}
    report = data.get("report") if isinstance(data, dict) else None
    if isinstance(report, dict) and report.get("score") is not None:
        return int(report["score"])
    return None


def build_my_admin_interview_from_assignment(
    assignment: LaunchedInterviewUser,
    launch: LaunchedInterview,
) -> dict:
    status = normalize_assignment_status(assignment.status)
    interview_id = launch.interview_id
    interview_url = None
    if interview_id:
        access_token = create_interview_access_token(
            user_id=assignment.user_id,
            interview_id=interview_id,
            assignment_id=assignment.id,
        )
        interview_url = build_relative_interview_url(assignment.user_id, interview_id, access_token)
    return {
        "id": assignment.id,
        "request_id": None,
        "interview_id": interview_id,
        "domain": launch.title,
        "description": launch.description,
        "status": status,
        "created_at": assignment.created_at or launch.launched_at,
        "launched_at": launch.launched_at,
        "completed_at": assignment.submitted_at if status == "completed" else None,
        "score": _score_from_assignment(assignment),
        "interview_url": interview_url,
        "user_id": assignment.user_id,
    }


def fetch_my_admin_interviews(db: Session, user_id: int) -> list[dict]:
    """Merge user-submitted requests and direct admin launches into one list."""
    request_rows = (
        db.query(InterviewRequest)
        .filter(InterviewRequest.user_id == user_id)
        .order_by(InterviewRequest.created_at.desc())
        .all()
    )
    linked_assignment_ids = {
        row.launched_interview_user_id
        for row in request_rows
        if row.launched_interview_user_id is not None
    }

    assignment_rows = (
        db.query(LaunchedInterviewUser, LaunchedInterview)
        .join(LaunchedInterview, LaunchedInterviewUser.launched_interview_id == LaunchedInterview.id)
        .filter(LaunchedInterviewUser.user_id == user_id)
        .order_by(LaunchedInterview.launched_at.desc())
        .all()
    )

    items: list[dict] = [build_my_admin_interview_item(row) for row in request_rows]

    for assignment, launch in assignment_rows:
        if assignment.id in linked_assignment_ids:
            continue
        items.append(build_my_admin_interview_from_assignment(assignment, launch))

    items.sort(
        key=lambda item: item.get("launched_at") or item.get("created_at"),
        reverse=True,
    )
    return items


def build_my_admin_interview_item(request: InterviewRequest) -> dict:
    interview_url = None
    if request.interview_id and request.status in {"pending", "in_progress", "completed"}:
        interview_url = build_relative_interview_url(request.user_id, request.interview_id)

    return {
        "id": request.id,
        "request_id": request.id,
        "interview_id": request.interview_id,
        "domain": request.domain,
        "description": request.description,
        "status": request.status,
        "created_at": request.created_at,
        "launched_at": request.launched_at,
        "completed_at": request.completed_at,
        "score": request.score,
        "interview_url": interview_url,
        "user_id": request.user_id,
    }


def build_admin_request_item(request: InterviewRequest, user: User | None = None) -> dict:
    user_name = ""
    if user:
        user_name = f"{user.first_name} {user.last_name}".strip() or user.email

    interview_url = None
    if request.interview_id and request.user_id and request.status != "requested":
        interview_url = build_interview_link(request.user_id, request.interview_id)

    return {
        "id": request.id,
        "user_id": request.user_id,
        "user_email": request.user_email,
        "user_name": user_name,
        "domain": request.domain,
        "description": request.description,
        "status": request.status,
        "created_at": request.created_at,
        "launched_at": request.launched_at,
        "interview_id": request.interview_id,
        "interview_url": interview_url,
        "score": request.score,
    }


def notify_admin_new_request(
    *,
    user_email: str,
    user_name: str,
    domain: str,
    description: str,
    request_id: int,
) -> None:
    send_new_interview_request_admin_email(
        user_email=user_email,
        user_name=user_name,
        domain=domain,
        description=description,
        request_id=request_id,
    )
