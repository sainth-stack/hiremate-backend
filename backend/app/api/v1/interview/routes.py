"""User live interview flow — questions, submit, performance review."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.interview import Interview
from backend.app.models.user import User
from backend.app.schemas.interview import (
    InterviewPerformanceResponse,
    InterviewQuestionAnalysisResponse,
    InterviewSubmitRequest,
    InterviewSubmitResponse,
    LiveInterviewQuestionsResponse,
)
from backend.app.services.interview_assignment import (
    get_user_assignment,
    normalize_assignment_status,
    require_matching_user,
)
from backend.app.services.interview_evaluation import evaluate_interview_submission
from backend.app.services.interview_questions import (
    ensure_interview_questions,
    to_question_card_responses,
)
from backend.app.services.interview_report import (
    build_report_response,
    get_stored_question_review,
)
from backend.app.services.interview_request_service import (
    mark_request_completed,
    mark_request_in_progress,
)

router = APIRouter()


def _build_submit_response(
    *,
    user_id: int,
    interview_id: int,
    report: dict,
) -> InterviewSubmitResponse:
    parsed = build_report_response(report)
    if not parsed:
        raise HTTPException(status_code=500, detail="Invalid evaluation report")
    return InterviewSubmitResponse(
        user_id=user_id,
        interview_id=interview_id,
        status="completed",
        **parsed.model_dump(),
    )


@router.get("/questions", response_model=LiveInterviewQuestionsResponse)
def get_interview_questions(
    user_id: int = Query(..., description="Logged-in user id from interview URL"),
    interview_id: int = Query(..., description="Interview template id from query string"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return ordered questions when the user clicks Start Interview.

    Frontend should call:
    GET /api/interview/questions?user_id={userId}&interview_id={interviewId}
    """
    require_matching_user(current_user.id, user_id)
    _assignment, _launch = get_user_assignment(db, user_id, interview_id)
    mark_request_in_progress(db, user_id, interview_id)

    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview template not found")

    try:
        rows = ensure_interview_questions(
            db,
            interview,
            user_id=current_user.id,
            email=current_user.email,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Question generation failed: {exc}",
        ) from exc

    return LiveInterviewQuestionsResponse(questions=to_question_card_responses(rows))


@router.post("/submit", response_model=InterviewSubmitResponse)
def submit_interview(
    body: InterviewSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evaluate all answers together via LangGraph and mark assignment completed."""
    require_matching_user(current_user.id, body.user_id)
    assignment, launch = get_user_assignment(db, body.user_id, body.interview_id)

    if normalize_assignment_status(assignment.status) == "completed":
        existing_report = (assignment.submission_data or {}).get("report")
        if existing_report:
            return _build_submit_response(
                user_id=body.user_id,
                interview_id=body.interview_id,
                report=existing_report,
            )
        raise HTTPException(status_code=400, detail="Interview already submitted")

    try:
        report = evaluate_interview_submission(
            user_id=body.user_id,
            email=current_user.email,
            interview_id=body.interview_id,
            title=launch.title,
            difficulty=launch.difficulty,
            jd=body.jd,
            answers=[item.model_dump() for item in body.answers],
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Interview evaluation failed: {exc}",
        ) from exc

    assignment.status = "completed"
    assignment.submitted_at = datetime.utcnow()
    assignment.submission_data = {
        "answers": [item.model_dump() for item in body.answers],
        "jd": body.jd,
        "report": report,
    }
    db.commit()

    display_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
    mark_request_completed(
        db,
        user_id=body.user_id,
        interview_id=body.interview_id,
        score=int(report.get("score", 0)),
        user_email=current_user.email,
        user_name=display_name,
        interview_title=launch.title,
    )

    return _build_submit_response(
        user_id=body.user_id,
        interview_id=body.interview_id,
        report=report,
    )


@router.get("/performance", response_model=InterviewPerformanceResponse)
def get_interview_performance(
    user_id: int = Query(..., description="User id"),
    interview_id: int = Query(..., description="Interview template id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Standalone performance/review endpoint — use anywhere in the UI
    after the interview is submitted (dashboard, profile, admin view, etc.).
    """
    require_matching_user(current_user.id, user_id)
    assignment, _launch = get_user_assignment(db, user_id, interview_id)

    status_value = normalize_assignment_status(assignment.status)
    report = build_report_response((assignment.submission_data or {}).get("report"))
    if status_value != "completed" or not report:
        raise HTTPException(
            status_code=404,
            detail="Interview performance report not available yet",
        )

    return InterviewPerformanceResponse(
        user_id=user_id,
        interview_id=interview_id,
        status=status_value,
        submitted_at=assignment.submitted_at,
        **report.model_dump(),
    )


@router.get("/question-analysis", response_model=InterviewQuestionAnalysisResponse)
def get_question_analysis(
    user_id: int = Query(..., description="Logged-in user id"),
    interview_id: int = Query(..., description="Interview template id"),
    order: int = Query(..., ge=1, description="1-based question order from results list"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Load full per-question review on demand when user expands a question card.

    Frontend: call only when user clicks "View full review" for question N.
    GET /api/interview/question-analysis?user_id=3&interview_id=2&order=1
    """
    require_matching_user(current_user.id, user_id)
    assignment, _launch = get_user_assignment(db, user_id, interview_id)

    if normalize_assignment_status(assignment.status) != "completed":
        raise HTTPException(status_code=404, detail="Interview not completed yet")

    stored_report = (assignment.submission_data or {}).get("report")
    review = get_stored_question_review(stored_report, order)
    if not review:
        raise HTTPException(status_code=404, detail=f"Question review not found for order {order}")

    return InterviewQuestionAnalysisResponse(
        user_id=user_id,
        interview_id=interview_id,
        **review.model_dump(),
    )
