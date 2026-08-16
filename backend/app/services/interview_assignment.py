"""Shared helpers for launched interview user assignments."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.launched_interview import LaunchedInterview, LaunchedInterviewUser
from backend.app.models.user import User


def require_matching_user(current_user_id: int, user_id: int) -> None:
    """Ensure the caller is the assigned candidate (write / live session)."""
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own interview",
        )


def resolve_interview_subject_user(
    db: Session,
    current_user: User,
    path_user_id: int,
    interview_id: int,
    *,
    read_only: bool = False,
) -> int:
    """
    Resolve which user's assignment to load.

    - Same account as the link: use path user id.
    - Admin read-only preview: may open any candidate link.
    - Logged-in user with their own assignment for this interview: use their id
      (handles stale/wrong user id in the URL).
    """
    if current_user.id == path_user_id:
        return path_user_id
    if read_only and getattr(current_user, "is_admin", False):
        return path_user_id
    if _has_user_assignment(db, current_user.id, interview_id):
        return current_user.id
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This interview link belongs to another account. Sign in with the invited candidate email.",
    )


def _has_user_assignment(db: Session, user_id: int, interview_id: int) -> bool:
    return (
        db.query(LaunchedInterviewUser.id)
        .join(LaunchedInterview, LaunchedInterviewUser.launched_interview_id == LaunchedInterview.id)
        .filter(
            LaunchedInterviewUser.user_id == user_id,
            LaunchedInterview.interview_id == interview_id,
        )
        .first()
        is not None
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


def resolve_frontend_base(
    *,
    override: str | None = None,
    origin: str | None = None,
) -> str:
    """Pick the public site origin: request body > Origin header > FRONTEND_URL env."""
    for candidate in (override, origin, settings.frontend_url):
        if not candidate:
            continue
        base = str(candidate).strip().rstrip("/")
        if base.startswith(("http://", "https://")):
            return base
    return settings.frontend_url.rstrip("/")


def build_interview_url(
    user_id: int,
    interview_id: int,
    access_token: str | None = None,
    *,
    frontend_base: str | None = None,
) -> str:
    """Full shareable interview URL."""
    base = resolve_frontend_base(override=frontend_base)
    url = f"{base}/interview/{user_id}?interview_id={interview_id}"
    if access_token:
        url = f"{url}&token={access_token}"
    return url


def build_relative_interview_url(
    user_id: int,
    interview_id: int,
    access_token: str | None = None,
    *,
    frontend_base: str | None = None,
) -> str:
    return build_interview_url(
        user_id,
        interview_id,
        access_token,
        frontend_base=frontend_base,
    )
