from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.interview_request import InterviewRequest
from backend.app.models.user import User
from backend.app.schemas.interview_request import (
    InterviewRequestCreateBody,
    InterviewRequestCreateResponse,
    MyAdminInterviewItem,
    MyAdminInterviewsResponse,
)
from backend.app.services.interview_request_service import (
    fetch_my_admin_interviews,
    notify_admin_new_request,
)

router = APIRouter()


@router.post(
    "/interview-requests",
    response_model=InterviewRequestCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_interview_request(
    body: InterviewRequestCreateBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User submits a request for an admin-managed interview."""
    request = InterviewRequest(
        user_id=current_user.id,
        user_email=current_user.email,
        domain=body.domain,
        description=body.description,
        status="requested",
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    display_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
    notify_admin_new_request(
        user_email=current_user.email,
        user_name=display_name,
        domain=request.domain,
        description=request.description,
        request_id=request.id,
    )

    return InterviewRequestCreateResponse(
        id=request.id,
        domain=request.domain,
        description=request.description,
        status=request.status,
        created_at=request.created_at,
    )


@router.get("/my-admin-interviews", response_model=MyAdminInterviewsResponse)
def list_my_admin_interviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the user's admin interviews: self-requested + direct admin launches."""
    items = fetch_my_admin_interviews(db, current_user.id)
    return MyAdminInterviewsResponse(
        interviews=[MyAdminInterviewItem(**item) for item in items]
    )
