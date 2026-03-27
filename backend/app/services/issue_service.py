"""
IssueService — CRUD for user-submitted issue reports.
Screenshot uploads are handled via the existing S3 service.
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.models.issue_report import IssueReport
from backend.app.schemas.issue import IssueCreateRequest, IssueStatusUpdateRequest

_MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024  # 5 MB


class IssueService:
    @staticmethod
    def create_issue(
        db: Session,
        data: IssueCreateRequest,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
    ) -> IssueReport:
        issue = IssueReport(
            title=data.title,
            description=data.description,
            category=data.category,
            status="open",
            source=data.source,
            user_id=user_id,
            user_email=user_email,
            issue_metadata=data.metadata,
        )
        db.add(issue)
        db.commit()
        db.refresh(issue)
        return issue

    @staticmethod
    def attach_screenshot(db: Session, issue: IssueReport, screenshot_url: str) -> IssueReport:
        issue.screenshot_url = screenshot_url
        db.commit()
        db.refresh(issue)
        return issue

    @staticmethod
    def list_issues(
        db: Session,
        status: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[IssueReport], int]:
        q = db.query(IssueReport)
        if status:
            q = q.filter(IssueReport.status == status)
        if category:
            q = q.filter(IssueReport.category == category)
        if source:
            q = q.filter(IssueReport.source == source)
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                IssueReport.title.ilike(pattern)
                | IssueReport.description.ilike(pattern)
                | IssueReport.user_email.ilike(pattern)
            )
        total = q.count()
        items = (
            q.order_by(IssueReport.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def get_issue(db: Session, issue_id: int) -> Optional[IssueReport]:
        return db.query(IssueReport).filter(IssueReport.id == issue_id).first()

    @staticmethod
    def update_status(
        db: Session, issue_id: int, data: IssueStatusUpdateRequest
    ) -> Optional[IssueReport]:
        issue = IssueService.get_issue(db, issue_id)
        if not issue:
            return None
        issue.status = data.status
        db.commit()
        db.refresh(issue)
        return issue

    @staticmethod
    def validate_screenshot(file_bytes: bytes, content_type: str) -> str:
        """Raises ValueError on invalid screenshot, returns normalized mime type."""
        allowed = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
        ct = content_type.lower().split(";")[0].strip()
        if ct not in allowed:
            raise ValueError(f"Unsupported file type: {ct}. Allowed: {allowed}")
        if len(file_bytes) > _MAX_SCREENSHOT_BYTES:
            raise ValueError("Screenshot must be under 5 MB")
        return ct
