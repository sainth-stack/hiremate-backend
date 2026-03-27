"""
Issue Report API routes.

Public (optional auth):
  POST /api/issues                  — submit a new issue

Admin-only:
  GET  /api/issues                  — list issues (filter, search, paginate)
  GET  /api/issues/{id}             — get single issue detail
  PATCH /api/issues/{id}/status     — update issue status
  POST  /api/issues/{id}/screenshot — attach a screenshot to an issue
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_admin_user, get_current_user_optional, get_db
from backend.app.models.user import User
from backend.app.schemas.issue import (
    IssueCreateRequest,
    IssueListResponse,
    IssueResponse,
    IssueStatusUpdateRequest,
)
from backend.app.services.issue_service import IssueService
from backend.app.services.s3_service import upload_file_to_s3
from backend.app.core.config import settings

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("", response_model=IssueResponse, status_code=201)
def create_issue(
    body: IssueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Submit a new issue. Works for both logged-in and anonymous users."""
    user_id = current_user.id if current_user else None
    user_email = current_user.email if current_user else None
    issue = IssueService.create_issue(db, body, user_id=user_id, user_email=user_email)
    return issue


@router.post("/{issue_id}/screenshot", response_model=IssueResponse)
async def upload_screenshot(
    issue_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Attach a screenshot to an existing issue. Uploads to S3."""
    issue = IssueService.get_issue(db, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    # Only the submitter (or admins) may attach screenshots
    if current_user and not current_user.is_admin:
        if issue.user_id and issue.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorised")

    file_bytes = await file.read()
    try:
        IssueService.validate_screenshot(file_bytes, file.content_type or "")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    file_name = f"issue-{issue_id}-{uuid.uuid4().hex[:8]}.png"
    uid = current_user.id if current_user else 0
    try:
        result = upload_file_to_s3(
            file_buffer=file_bytes,
            file_name=file_name,
            user_id=uid,
            mime_type=file.content_type or "image/png",
            key_prefix="issue-screenshots",
        )
        screenshot_url = result.get("url") or result.get("key", "")
    except Exception:
        # S3 not configured — store locally as fallback
        import os
        local_dir = "uploads/screenshots"
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, file_name)
        with open(local_path, "wb") as fh:
            fh.write(file_bytes)
        screenshot_url = f"/{local_dir}/{file_name}"

    issue = IssueService.attach_screenshot(db, issue, screenshot_url)
    return issue


@router.get("", response_model=IssueListResponse)
def list_issues(
    status: str | None = Query(None),
    category: str | None = Query(None),
    source: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """List all issues with optional filters. Admin only."""
    items, total = IssueService.list_issues(
        db,
        status=status,
        category=category,
        source=source,
        search=search,
        page=page,
        page_size=page_size,
    )
    return IssueListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{issue_id}", response_model=IssueResponse)
def get_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Get single issue detail. Admin only."""
    issue = IssueService.get_issue(db, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@router.patch("/{issue_id}/status", response_model=IssueResponse)
def update_issue_status(
    issue_id: int,
    body: IssueStatusUpdateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Update issue status. Admin only."""
    issue = IssueService.update_status(db, issue_id, body)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue
