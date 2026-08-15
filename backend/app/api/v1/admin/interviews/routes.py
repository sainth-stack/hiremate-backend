from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_admin_user, get_db
from backend.app.models.interview import Interview
from backend.app.models.interview_question import InterviewQuestion
from backend.app.models.launched_interview import LaunchedInterview, LaunchedInterviewUser
from backend.app.models.user import User
from backend.app.services.interview_question_generator import generate_interview_questions
from backend.app.services.interview_question_generator.persistence import (
    build_interview_detail,
    load_interview_questions,
    save_interview_questions,
)
from backend.app.services.interview_email_service import send_interview_invitation_email
from backend.app.services.interview_assignment import build_relative_interview_url
from backend.app.schemas.interview import (
    InterviewCreateRequest,
    InterviewDetailResponse,
    InterviewListResponse,
    InterviewResponse,
    InterviewUpdateRequest,
    LaunchAssignmentResponse,
    LaunchInterviewRequest,
    LaunchInterviewResponse,
)

router = APIRouter()


@router.get("/interviews", response_model=InterviewListResponse)
def list_interviews(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """List all admin-managed interviews."""
    interviews = db.query(Interview).order_by(Interview.created_at.desc()).all()
    return InterviewListResponse(interviews=interviews)


@router.get("/interviews/{interview_id}", response_model=InterviewDetailResponse)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Get interview template with generated question cards."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.interview_id == interview_id)
        .order_by(InterviewQuestion.order_index)
        .all()
    )
    return build_interview_detail(interview, questions)


@router.post(
    "/interviews",
    response_model=InterviewDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_interview(
    body: InterviewCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Create interview template and generate 15 LangGraph question cards from description."""
    try:
        generated = generate_interview_questions(
            title=body.title,
            description=body.description,
            difficulty=body.difficulty,
            user_id=admin.id,
            email=admin.email,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Question generation failed: {exc}",
        ) from exc

    interview = Interview(
        title=body.title,
        difficulty=body.difficulty,
        description=body.description,
    )
    db.add(interview)
    db.flush()

    question_rows = save_interview_questions(db, interview.id, generated)
    db.commit()
    db.refresh(interview)
    return build_interview_detail(interview, question_rows)


@router.put("/interviews/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: int,
    body: InterviewUpdateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Update an admin-managed interview."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    interview.title = body.title
    interview.difficulty = body.difficulty
    interview.description = body.description
    db.commit()
    db.refresh(interview)
    return interview


@router.delete("/interviews/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Delete an admin-managed interview."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    db.delete(interview)
    db.commit()


def _resolve_launch_assignees(
    db: Session,
    users: list[tuple[int, str]],
) -> list[tuple[int, str, str]]:
    """Validate users and return (user_id, email, display_name) tuples."""
    seen_ids: set[int] = set()
    assignees: list[tuple[int, str, str]] = []

    for user_id, email in users:
        if user_id in seen_ids:
            continue
        seen_ids.add(user_id)

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=400, detail=f"User with id {user_id} not found")

        if email != user.email.lower():
            raise HTTPException(
                status_code=400,
                detail=f"Email mismatch for user id {user_id}",
            )
        display_name = f"{user.first_name} {user.last_name}".strip() or user.email
        assignees.append((user.id, user.email, display_name))

    return assignees


@router.post(
    "/launch-interviews",
    response_model=LaunchInterviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def launch_interview(
    body: LaunchInterviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Launch an interview template to selected users."""
    interview = db.query(Interview).filter(Interview.id == body.interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    assignees = _resolve_launch_assignees(
        db,
        [(user.id, user.email) for user in body.users],
    )

    launch = LaunchedInterview(
        interview_id=body.interview_id,
        title=body.title.strip(),
        difficulty=body.difficulty,
        description=body.description,
        interview_created_at=body.created_at,
        launched_by_user_id=admin.id,
    )
    db.add(launch)
    db.flush()

    for user_id, user_email, _display_name in assignees:
        db.add(
            LaunchedInterviewUser(
                launched_interview_id=launch.id,
                user_id=user_id,
                user_email=user_email,
            )
        )

    db.commit()
    db.refresh(launch)

    question_rows = load_interview_questions(db, body.interview_id)
    interview_detail = build_interview_detail(interview, question_rows)

    assignments: list[LaunchAssignmentResponse] = []
    for user_id, user_email, display_name in assignees:
        send_interview_invitation_email(
            to_email=user_email,
            user_id=user_id,
            interview_id=launch.interview_id,
            title=launch.title,
            difficulty=launch.difficulty,
            description=launch.description,
            user_name=display_name,
        )
        assignments.append(
            LaunchAssignmentResponse(
                user_id=user_id,
                interview_id=launch.interview_id,
                url=build_relative_interview_url(user_id, launch.interview_id),
            )
        )

    return LaunchInterviewResponse(
        launched_count=len(assignments),
        interview=interview_detail,
        assignments=assignments,
    )
