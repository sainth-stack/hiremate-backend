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
    InterviewRetestRequest,
    InterviewRetestResponse,
    InterviewSubmitRequest,
    InterviewSubmitResponse,
    LiveInterviewQuestionsResponse,
)
from backend.app.services.interview_assignment import (
    get_user_assignment,
    normalize_assignment_status,
    resolve_interview_subject_user,
)
from backend.app.services.interview_evaluation import evaluate_interview_submission
from backend.app.services.interview_questions import (
    ensure_interview_questions,
    to_question_card_responses,
)
from backend.app.services.voice.audio_lookup import find_answer_audio
from backend.app.services.voice.voice_config import resolve_launch_voice_config, resolve_question_count
from backend.app.services.interview_report import (
    build_report_response,
    get_stored_question_review,
)
from backend.app.services.interview_request_service import (
    mark_request_completed,
    mark_request_in_progress,
)

router = APIRouter()


def _enrich_submit_answers(
    db: Session,
    interview: Interview,
    answers: list,
    *,
    user_id: int,
    email: str | None,
) -> list[dict]:
    rows = ensure_interview_questions(db, interview, user_id=user_id, email=email)
    by_text = {
        (row.question_text or "").strip().lower(): row
        for row in rows
    }
    by_order = {
        int(row.order_index): row
        for row in rows
        if row.order_index is not None
    }

    enriched: list[dict] = []
    for index, item in enumerate(answers, start=1):
        payload = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        question_text = (payload.get("question") or "").strip()
        meta = by_text.get(question_text.lower())
        if not meta:
            meta = by_order.get(int(payload.get("order") or index))
        if meta:
            payload["category"] = meta.category
            payload["complexity"] = meta.complexity
            payload["template"] = meta.template
            payload["expectations"] = meta.expectations
        enriched.append(payload)
    return enriched


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
    subject_user_id = resolve_interview_subject_user(
        db, current_user, user_id, interview_id, read_only=False,
    )
    _assignment, launch = get_user_assignment(db, subject_user_id, interview_id)
    mark_request_in_progress(db, subject_user_id, interview_id)

    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview template not found")

    try:
        rows = ensure_interview_questions(
            db,
            interview,
            user_id=subject_user_id,
            email=current_user.email,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Question generation failed: {exc}",
        ) from exc

    question_count = resolve_question_count(interview, launch)
    limited_rows = rows[:question_count]
    voice = resolve_launch_voice_config(db, launch)

    return LiveInterviewQuestionsResponse(
        questions=to_question_card_responses(limited_rows),
        question_count=question_count,
        voice_provider=voice.provider,
        voice_id=voice.voice_id,
        voice_label=voice.display_name,
        tts_speaker=voice.voice_id if voice.provider == "sarvam" else None,
        tts_language_code=voice.language_code,
    )


@router.post("/submit", response_model=InterviewSubmitResponse)
def submit_interview(
    body: InterviewSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evaluate all answers together via LangGraph and mark assignment completed."""
    subject_user_id = resolve_interview_subject_user(
        db, current_user, body.user_id, body.interview_id, read_only=False,
    )
    assignment, launch = get_user_assignment(db, subject_user_id, body.interview_id)

    if normalize_assignment_status(assignment.status) == "completed":
        existing_report = (assignment.submission_data or {}).get("report")
        if existing_report:
            return _build_submit_response(
                user_id=subject_user_id,
                interview_id=body.interview_id,
                report=existing_report,
            )
        raise HTTPException(status_code=400, detail="Interview already submitted")

    interview = db.query(Interview).filter(Interview.id == body.interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview template not found")

    enriched_answers = _enrich_submit_answers(
        db,
        interview,
        body.answers,
        user_id=subject_user_id,
        email=current_user.email,
    )

    try:
        report = evaluate_interview_submission(
            user_id=subject_user_id,
            email=current_user.email,
            interview_id=body.interview_id,
            title=launch.title,
            difficulty=launch.difficulty,
            jd=body.jd,
            answers=enriched_answers,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Interview evaluation failed: {exc}",
        ) from exc

    assignment.status = "completed"
    assignment.submitted_at = datetime.utcnow()
    existing_data = assignment.submission_data or {}
    assignment.submission_data = {
        **existing_data,
        "answers": [item.model_dump() for item in body.answers],
        "jd": body.jd,
        "report": report,
    }
    db.commit()

    display_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
    mark_request_completed(
        db,
        user_id=subject_user_id,
        interview_id=body.interview_id,
        score=int(report.get("score", 0)),
        user_email=current_user.email,
        user_name=display_name,
        interview_title=launch.title,
    )

    return _build_submit_response(
        user_id=subject_user_id,
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
    subject_user_id = resolve_interview_subject_user(
        db, current_user, user_id, interview_id, read_only=True,
    )
    assignment, _launch = get_user_assignment(db, subject_user_id, interview_id)

    status_value = normalize_assignment_status(assignment.status)
    report = build_report_response((assignment.submission_data or {}).get("report"))
    if status_value != "completed" or not report:
        raise HTTPException(
            status_code=404,
            detail="Interview performance report not available yet",
        )

    return InterviewPerformanceResponse(
        user_id=subject_user_id,
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
    subject_user_id = resolve_interview_subject_user(
        db, current_user, user_id, interview_id, read_only=True,
    )
    assignment, _launch = get_user_assignment(db, subject_user_id, interview_id)

    if normalize_assignment_status(assignment.status) != "completed":
        raise HTTPException(status_code=404, detail="Interview not completed yet")

    stored_report = (assignment.submission_data or {}).get("report")
    review = get_stored_question_review(stored_report, order)
    if not review:
        raise HTTPException(status_code=404, detail=f"Question review not found for order {order}")

    audio_item = find_answer_audio(assignment.submission_data, order=order)
    audio_key = audio_item.get("audio_key") if audio_item else None

    payload = review.model_dump()
    payload.update(
        {
            "user_id": user_id,
            "interview_id": interview_id,
            "audio_key": audio_key,
            "has_audio": bool(audio_key),
        }
    )
    return InterviewQuestionAnalysisResponse(**payload)


@router.post("/retest", response_model=InterviewRetestResponse)
def retest_interview(
    body: InterviewRetestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset a completed interview so the candidate can take it again."""
    subject_user_id = resolve_interview_subject_user(
        db, current_user, body.user_id, body.interview_id, read_only=False,
    )
    assignment, _launch = get_user_assignment(db, subject_user_id, body.interview_id)

    assignment.status = "pending"
    assignment.submitted_at = None
    assignment.submission_data = None
    db.commit()

    return InterviewRetestResponse(
        user_id=subject_user_id,
        interview_id=body.interview_id,
        status="pending",
    )
