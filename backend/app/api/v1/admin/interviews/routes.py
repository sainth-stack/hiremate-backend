from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_admin_user, get_db
from backend.app.models.interview import Interview
from backend.app.models.interview_question import InterviewQuestion
from backend.app.models.launched_interview import LaunchedInterview, LaunchedInterviewUser
from backend.app.models.user import User
from backend.app.services.voice.cartesia_service import resolve_voice_storage_id
from backend.app.services.voice.custom_voice_service import list_active_custom_voices
from backend.app.services.interview_question_generator import generate_interview_questions
from backend.app.services.interview_question_generator.question_count import resolve_question_count
from backend.app.services.interview_question_generator.persistence import (
    build_interview_detail,
    load_interview_questions,
    save_interview_questions,
)
from backend.app.services.interview_email_service import send_interview_invitation_email
from backend.app.services.interview_summary import generate_interview_summary, resolve_interview_summary
from backend.app.services.interview_assignment import build_interview_url, resolve_frontend_base
from backend.app.services.interview_access import create_interview_access_token
from backend.app.schemas.interview import (
    InterviewCreateRequest,
    InterviewDetailResponse,
    InterviewListResponse,
    InterviewQuestionsUpdateRequest,
    InterviewRegenerateQuestionsRequest,
    InterviewResponse,
    InterviewUpdateRequest,
    LaunchAssignmentResponse,
    LaunchCampaignDetailResponse,
    LaunchCampaignListResponse,
    LaunchInterviewRequest,
    LaunchInterviewResponse,
)
from backend.app.services.launch_campaign_service import get_launch_campaign_detail, list_launch_campaigns

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
            question_count=body.question_count,
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
        summary=generate_interview_summary(
            title=body.title,
            description=body.description,
            difficulty=body.difficulty,
            user_id=admin.id,
            email=admin.email,
        ),
        question_count=body.question_count,
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

    title_changed = interview.title != body.title
    difficulty_changed = interview.difficulty != body.difficulty
    description_changed = interview.description != body.description
    interview.title = body.title
    interview.difficulty = body.difficulty
    interview.description = body.description
    interview.question_count = body.question_count
    if title_changed or difficulty_changed or description_changed:
        interview.summary = generate_interview_summary(
            title=body.title,
            description=body.description,
            difficulty=body.difficulty,
            user_id=_admin.id,
            email=_admin.email,
        )
    db.commit()
    db.refresh(interview)
    return interview


@router.patch("/interviews/{interview_id}/questions", response_model=InterviewDetailResponse)
def update_interview_questions(
    interview_id: int,
    body: InterviewQuestionsUpdateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Update question wording for an interview template."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    existing = {
        row.id: row
        for row in db.query(InterviewQuestion)
        .filter(InterviewQuestion.interview_id == interview_id)
        .all()
    }
    for item in body.questions:
        row = existing.get(item.id)
        if not row:
            raise HTTPException(
                status_code=400,
                detail=f"Question id {item.id} not found for this interview",
            )
        row.question_text = item.question_text.strip()
        if row.view_card and isinstance(row.view_card, dict):
            view_card = dict(row.view_card)
            view_card["question"] = item.question_text.strip()
            row.view_card = view_card

    db.commit()
    questions = load_interview_questions(db, interview_id)
    return build_interview_detail(interview, questions)


@router.post("/interviews/{interview_id}/regenerate-questions", response_model=InterviewDetailResponse)
def regenerate_interview_questions(
    interview_id: int,
    body: InterviewRegenerateQuestionsRequest | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Regenerate all questions from the interview description."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    payload = body or InterviewRegenerateQuestionsRequest()
    question_count = resolve_question_count(
        interview.question_count,
        interview.description,
        requested_count=payload.question_count,
    )
    interview.question_count = question_count
    interview.summary = generate_interview_summary(
        title=interview.title,
        description=interview.description,
        difficulty=interview.difficulty,
        user_id=admin.id,
        email=admin.email,
    )

    try:
        generated = generate_interview_questions(
            title=interview.title,
            description=interview.description,
            difficulty=interview.difficulty,
            user_id=admin.id,
            email=admin.email,
            question_count=question_count,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Question generation failed: {exc}",
        ) from exc

    db.query(InterviewQuestion).filter(InterviewQuestion.interview_id == interview_id).delete()
    question_rows = save_interview_questions(db, interview.id, generated)
    db.commit()
    db.refresh(interview)
    return build_interview_detail(interview, question_rows)


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
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Launch an interview template to selected users."""
    frontend_base = resolve_frontend_base(
        override=body.frontend_url,
        origin=request.headers.get("origin"),
    )
    interview = db.query(Interview).filter(Interview.id == body.interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    assignees = _resolve_launch_assignees(
        db,
        [(user.id, user.email) for user in body.users],
    )

    allowed_custom = {voice.cartesia_voice_id for voice in list_active_custom_voices(db)}
    custom_labels = {voice.cartesia_voice_id: voice.name for voice in list_active_custom_voices(db)}
    storage_voice_id, resolved_label = resolve_voice_storage_id(
        body.voice_id,
        allowed_custom_ids=allowed_custom,
        custom_labels=custom_labels,
    )

    launch = LaunchedInterview(
        interview_id=body.interview_id,
        title=body.title.strip(),
        launch_name=(body.launch_name or body.title).strip()[:255],
        difficulty=body.difficulty,
        description=body.description,
        summary=resolve_interview_summary(
            title=interview.title,
            description=interview.description,
            difficulty=interview.difficulty,
            summary=interview.summary,
        ),
        interview_created_at=body.created_at,
        launched_by_user_id=admin.id,
        voice_provider="cartesia",
        voice_id=storage_voice_id,
        voice_label=(body.voice_label or resolved_label or storage_voice_id)[:255],
        tts_language_code=body.tts_language_code or "en-IN",
        question_count=interview.question_count or 15,
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

    assignment_rows = (
        db.query(LaunchedInterviewUser)
        .filter(LaunchedInterviewUser.launched_interview_id == launch.id)
        .all()
    )
    name_by_user_id = {user_id: display_name for user_id, _email, display_name in assignees}

    assignments: list[LaunchAssignmentResponse] = []
    for row in assignment_rows:
        access_token = create_interview_access_token(
            user_id=row.user_id,
            interview_id=launch.interview_id,
            assignment_id=row.id,
        )
        display_name = name_by_user_id.get(row.user_id)
        send_interview_invitation_email(
            to_email=row.user_email,
            user_id=row.user_id,
            interview_id=launch.interview_id,
            title=launch.title,
            difficulty=launch.difficulty,
            summary=resolve_interview_summary(
                title=launch.title,
                description=launch.description,
                difficulty=launch.difficulty,
                summary=launch.summary,
            ),
            user_name=display_name,
            access_token=access_token,
            frontend_base=frontend_base,
        )
        assignments.append(
            LaunchAssignmentResponse(
                user_id=row.user_id,
                interview_id=launch.interview_id,
                url=build_interview_url(
                    row.user_id,
                    launch.interview_id,
                    access_token,
                    frontend_base=frontend_base,
                ),
            )
        )

    return LaunchInterviewResponse(
        launched_count=len(assignments),
        interview=interview_detail,
        assignments=assignments,
    )


@router.get("/launches", response_model=LaunchCampaignListResponse)
def list_launches(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """List all launched interview campaigns with assignee status counts."""
    return list_launch_campaigns(db, page=page, limit=limit)


@router.get("/launches/{launch_id}", response_model=LaunchCampaignDetailResponse)
def get_launch_detail(
    launch_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Full launch campaign detail including assignee transcripts and evaluation results."""
    detail = get_launch_campaign_detail(db, launch_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Launch campaign not found")
    return detail


@router.delete("/launches/{launch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_launch(
    launch_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Delete a launch campaign and all assignee records."""
    launch = db.query(LaunchedInterview).filter(LaunchedInterview.id == launch_id).first()
    if not launch:
        raise HTTPException(status_code=404, detail="Launch campaign not found")

    db.delete(launch)
    db.commit()
