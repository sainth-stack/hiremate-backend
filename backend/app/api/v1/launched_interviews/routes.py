from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.interview import Interview
from backend.app.models.user import User
from backend.app.schemas.interview import (
    InterviewIntroResponse,
    SubmitLaunchedInterviewRequest,
    SubmitLaunchedInterviewResponse,
    UserLaunchedInterviewResponse,
)
from backend.app.services.interview_assignment import (
    get_user_assignment,
    normalize_assignment_status,
    require_matching_user,
    resolve_interview_subject_user,
)
from backend.app.services.interview_questions import ensure_interview_questions, to_question_card_responses
from backend.app.services.interview_report import build_report_response
from backend.app.services.voice.voice_config import resolve_launch_voice_config, resolve_question_count
from backend.app.services.interview_summary import resolve_interview_summary

router = APIRouter()


def _extract_report(submission_data: dict | None):
    if not submission_data:
        return None
    return build_report_response(submission_data.get("report"))


@router.get("/launched-interviews/user/{user_id}", response_model=UserLaunchedInterviewResponse)
def get_user_launched_interview(
    user_id: int,
    interview_id: int = Query(..., description="Interview template id from the link"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return intro metadata for the live interview page."""
    subject_user_id = resolve_interview_subject_user(
        db, current_user, user_id, interview_id, read_only=True,
    )
    assignment, launch = get_user_assignment(db, subject_user_id, interview_id)

    status_value = normalize_assignment_status(assignment.status)
    report = _extract_report(assignment.submission_data) if status_value == "completed" else None

    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview template not found")

    try:
        question_rows = ensure_interview_questions(
            db,
            interview,
            user_id=subject_user_id,
            email=assignment.user_email or current_user.email,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Question generation failed: {exc}",
        ) from exc

    question_count = resolve_question_count(interview, launch)
    voice = resolve_launch_voice_config(db, launch)

    display_summary = resolve_interview_summary(
        title=launch.title,
        description=launch.description,
        difficulty=launch.difficulty,
        summary=launch.summary or interview.summary,
    )

    return UserLaunchedInterviewResponse(
        status=status_value,
        user_email=assignment.user_email,
        interview=InterviewIntroResponse(
            id=launch.interview_id,
            title=launch.title,
            difficulty=launch.difficulty,
            description=launch.description,
            summary=display_summary,
            created_at=launch.interview_created_at or launch.launched_at,
            question_count=question_count,
            tts_speaker=voice.voice_id if voice.provider == "sarvam" else None,
            tts_language_code=voice.language_code,
            questions=to_question_card_responses(question_rows[:question_count]),
        ),
        report=report,
    )


@router.post(
    "/launched-interviews/user/{user_id}/submit",
    response_model=SubmitLaunchedInterviewResponse,
    deprecated=True,
)
def submit_user_launched_interview(
    user_id: int,
    body: SubmitLaunchedInterviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Legacy submit endpoint — prefer POST /api/interview/submit."""
    require_matching_user(current_user.id, user_id)
    assignment, launch = get_user_assignment(db, user_id, body.interview_id)

    if normalize_assignment_status(assignment.status) == "completed":
        raise HTTPException(status_code=400, detail="Interview already submitted")

    submission_data = {}
    if body.answers is not None:
        submission_data["answers"] = body.answers
    if body.notes:
        submission_data["notes"] = body.notes.strip()

    assignment.status = "completed"
    assignment.submitted_at = datetime.utcnow()
    assignment.submission_data = submission_data or None
    db.commit()
    db.refresh(assignment)

    return SubmitLaunchedInterviewResponse(
        interview_id=launch.interview_id,
        user_id=user_id,
        status=assignment.status,
        submitted_at=assignment.submitted_at,
    )
