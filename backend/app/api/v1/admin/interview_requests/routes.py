from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_admin_user, get_db
from backend.app.models.interview import Interview
from backend.app.models.interview_request import InterviewRequest
from backend.app.models.user import User
from backend.app.schemas.interview_request import (
    AdminInterviewRequestItem,
    AdminInterviewRequestListResponse,
    LaunchInterviewRequestBody,
    LaunchInterviewRequestResponse,
)
from backend.app.services.interview_request_service import (
    build_admin_request_item,
    launch_from_interview_request,
)

router = APIRouter()


@router.get("/interview-requests", response_model=AdminInterviewRequestListResponse)
def list_interview_requests(
    status: str | None = Query(None, description="Filter by status e.g. requested"),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Admin list of user interview requests."""
    query = db.query(InterviewRequest, User).join(User, InterviewRequest.user_id == User.id)
    if status:
        query = query.filter(InterviewRequest.status == status.strip().lower())
    rows = query.order_by(InterviewRequest.created_at.desc()).all()

    return AdminInterviewRequestListResponse(
        requests=[
            AdminInterviewRequestItem(**build_admin_request_item(request, user))
            for request, user in rows
        ]
    )


@router.get("/interview-requests/{request_id}", response_model=AdminInterviewRequestItem)
def get_interview_request(
    request_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Full details for a single interview request."""
    row = (
        db.query(InterviewRequest, User)
        .join(User, InterviewRequest.user_id == User.id)
        .filter(InterviewRequest.id == request_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Interview request not found")
    request, user = row
    return AdminInterviewRequestItem(**build_admin_request_item(request, user))


@router.post(
    "/interview-requests/{request_id}/launch",
    response_model=LaunchInterviewRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def launch_interview_request(
    request_id: int,
    body: LaunchInterviewRequestBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Send an interview template to the user who submitted the request."""
    request = db.query(InterviewRequest).filter(InterviewRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Interview request not found")

    if request.status not in {"requested"}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot launch request with status '{request.status}'",
        )

    if body.user_id != request.user_id:
        raise HTTPException(status_code=400, detail="user_id does not match request owner")
    if body.user_email != request.user_email.lower():
        raise HTTPException(status_code=400, detail="user_email does not match request owner")

    interview = db.query(Interview).filter(Interview.id == body.interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview template not found")

    try:
        _launch, _assignment, interview_url = launch_from_interview_request(
            db,
            request=request,
            interview=interview,
            title=body.title,
            difficulty=body.difficulty,
            description=body.description,
            admin_user_id=admin.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LaunchInterviewRequestResponse(
        launched_count=1,
        interview_url=interview_url,
        status="pending",
        request_id=request.id,
        interview_id=body.interview_id,
        user_id=request.user_id,
    )
