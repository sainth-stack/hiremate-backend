"""Shared helpers for launched interview user assignments."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.launched_interview import LaunchedInterview, LaunchedInterviewUser


def require_matching_user(current_user_id: int, user_id: int) -> None:
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own interview",
        )


def normalize_assignment_status(status_value: str | None) -> str:
    """Map DB status to frontend contract: pending | in_progress | completed."""
    if status_value in {"submitted", "completed"}:
        return "completed"
    if status_value == "in_progress":
        return "in_progress"
    return "pending"


def get_user_assignment(
    db: Session,
    user_id: int,
    interview_id: int,
) -> tuple[LaunchedInterviewUser, LaunchedInterview]:
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
    if not assignment:
        raise HTTPException(status_code=404, detail="Interview assignment not found")

    launch = assignment.launch or db.query(LaunchedInterview).filter(
        LaunchedInterview.id == assignment.launched_interview_id
    ).first()
    if not launch:
        raise HTTPException(status_code=404, detail="Launched interview not found")
    return assignment, launch


def build_relative_interview_url(user_id: int, interview_id: int) -> str:
    return f"/interview/{user_id}?interview_id={interview_id}"
