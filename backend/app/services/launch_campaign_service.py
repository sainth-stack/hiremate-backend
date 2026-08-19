"""Admin views of launched interview campaigns."""
from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from backend.app.models.launched_interview import LaunchedInterview, LaunchedInterviewUser
from backend.app.models.user import User
from backend.app.schemas.interview import (
    LaunchCampaignAssigneeDetail,
    LaunchCampaignAssigneeSummary,
    LaunchCampaignAnswerItem,
    LaunchCampaignDetailResponse,
    LaunchCampaignListResponse,
    LaunchCampaignSummary,
)
from backend.app.services.interview_summary import resolve_interview_summary
from backend.app.services.interview_assignment import (
    build_interview_url,
    normalize_assignment_status,
)
from backend.app.services.interview_access import create_interview_access_token
from backend.app.services.interview_report import build_report_response, parse_question_review
from backend.app.services.voice.audio_lookup import find_answer_audio, list_answer_audio_items


def _display_launch_name(launch: LaunchedInterview) -> str:
    if launch.launch_name and launch.launch_name.strip():
        return launch.launch_name.strip()
    return launch.title


def _score_from_submission(submission_data: dict | None) -> int | None:
    if not submission_data or not isinstance(submission_data, dict):
        return None
    report = submission_data.get("report") or {}
    if not isinstance(report, dict):
        return None
    for key in ("score", "overall_score", "final_score"):
        value = report.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return None


def _user_display_name(user: User | None, fallback_email: str) -> str | None:
    if not user:
        return fallback_email or None
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or user.email


def _count_by_status(assignments: list[LaunchedInterviewUser]) -> tuple[int, int, int]:
    completed = in_progress = pending = 0
    for row in assignments:
        status = normalize_assignment_status(row.status)
        if status == "completed":
            completed += 1
        elif status == "in_progress":
            in_progress += 1
        else:
            pending += 1
    return completed, in_progress, pending


def _build_assignee_summary(
    row: LaunchedInterviewUser,
    user: User | None,
    interview_id: int,
) -> LaunchCampaignAssigneeSummary:
    status = normalize_assignment_status(row.status)
    return LaunchCampaignAssigneeSummary(
        id=row.id,
        user_id=row.user_id,
        user_email=row.user_email,
        user_name=_user_display_name(user, row.user_email),
        status=status,
        submitted_at=row.submitted_at,
        score=_score_from_submission(row.submission_data) if status == "completed" else None,
        interview_url=build_interview_url(
            row.user_id,
            interview_id,
            create_interview_access_token(
                user_id=row.user_id,
                interview_id=interview_id,
                assignment_id=row.id,
            ),
        ),
    )


def list_launch_campaigns(db: Session, *, page: int = 1, limit: int = 50) -> LaunchCampaignListResponse:
    offset = max(page - 1, 0) * limit
    base_query = db.query(LaunchedInterview).order_by(LaunchedInterview.launched_at.desc())
    total = base_query.count()
    launches = (
        base_query
        .options(joinedload(LaunchedInterview.assignments))
        .offset(offset)
        .limit(limit)
        .all()
    )

    launcher_ids = {launch.launched_by_user_id for launch in launches if launch.launched_by_user_id}
    launchers: dict[int, User] = {}
    if launcher_ids:
        launchers = {
            user.id: user
            for user in db.query(User).filter(User.id.in_(launcher_ids)).all()
        }

    summaries: list[LaunchCampaignSummary] = []
    for launch in launches:
        completed, in_progress, pending = _count_by_status(launch.assignments or [])
        launcher = launchers.get(launch.launched_by_user_id) if launch.launched_by_user_id else None
        summaries.append(
            LaunchCampaignSummary(
                id=launch.id,
                launch_name=_display_launch_name(launch),
                interview_id=launch.interview_id,
                interview_title=launch.title,
                difficulty=launch.difficulty,
                launched_at=launch.launched_at,
                launched_by_name=_user_display_name(launcher, launcher.email if launcher else ""),
                launched_by_email=launcher.email if launcher else None,
                total_assignees=len(launch.assignments or []),
                completed_count=completed,
                in_progress_count=in_progress,
                pending_count=pending,
            )
        )

    return LaunchCampaignListResponse(launches=summaries, total=total)


def get_launch_campaign_detail(db: Session, launch_id: int) -> LaunchCampaignDetailResponse | None:
    launch = (
        db.query(LaunchedInterview)
        .options(joinedload(LaunchedInterview.assignments))
        .filter(LaunchedInterview.id == launch_id)
        .first()
    )
    if not launch:
        return None

    user_ids = [row.user_id for row in launch.assignments or []]
    users_by_id: dict[int, User] = {}
    if user_ids:
        users_by_id = {
            user.id: user
            for user in db.query(User).filter(User.id.in_(user_ids)).all()
        }

    launcher = None
    if launch.launched_by_user_id:
        launcher = db.query(User).filter(User.id == launch.launched_by_user_id).first()

    completed, in_progress, pending = _count_by_status(launch.assignments or [])

    assignee_details: list[LaunchCampaignAssigneeDetail] = []
    for row in sorted(launch.assignments or [], key=lambda x: x.created_at or launch.launched_at):
        user = users_by_id.get(row.user_id)
        summary = _build_assignee_summary(row, user, launch.interview_id)
        submission = row.submission_data if isinstance(row.submission_data, dict) else {}
        report_raw = submission.get("report")
        report = build_report_response(report_raw) if report_raw else None

        answers_raw = submission.get("answers") or []
        checkpoint_items = list_answer_audio_items(submission)
        answers: list[LaunchCampaignAnswerItem] = []
        if isinstance(answers_raw, list) and answers_raw:
            for index, item in enumerate(answers_raw, start=1):
                if isinstance(item, dict):
                    order = int(item.get("order") or index)
                    audio_key = item.get("audio_key")
                    answers.append(
                        LaunchCampaignAnswerItem(
                            question=str(item.get("question") or ""),
                            answer=str(item.get("answer") or ""),
                            order=order,
                            audio_key=audio_key,
                            audio_url=item.get("audio_url"),
                            has_audio=bool(audio_key),
                            video_key=item.get("video_key"),
                            video_url=item.get("video_url"),
                            has_video=bool(item.get("video_key")),
                        )
                    )
        elif checkpoint_items:
            for item in checkpoint_items:
                answers.append(
                    LaunchCampaignAnswerItem(
                        question=str(item.get("question") or ""),
                        answer=str(item.get("transcript") or item.get("answer") or ""),
                        order=int(item.get("order") or 0) or None,
                        audio_key=item.get("audio_key"),
                        audio_url=item.get("audio_url"),
                        has_audio=bool(item.get("audio_key")),
                        video_key=item.get("video_key"),
                        video_url=item.get("video_url"),
                        has_video=bool(item.get("video_key")),
                    )
                )

        question_reviews = []
        if isinstance(report_raw, dict):
            for index, item in enumerate(report_raw.get("question_reviews") or [], start=1):
                if isinstance(item, dict):
                    question_reviews.append(parse_question_review(item, index))

        assignee_details.append(
            LaunchCampaignAssigneeDetail(
                **summary.model_dump(),
                answers=answers,
                report=report,
                question_reviews=question_reviews,
            )
        )

    return LaunchCampaignDetailResponse(
        id=launch.id,
        launch_name=_display_launch_name(launch),
        interview_id=launch.interview_id,
        interview_title=launch.title,
        difficulty=launch.difficulty,
        launched_at=launch.launched_at,
        launched_by_name=_user_display_name(launcher, launcher.email if launcher else ""),
        launched_by_email=launcher.email if launcher else None,
        total_assignees=len(launch.assignments or []),
        completed_count=completed,
        in_progress_count=in_progress,
        pending_count=pending,
        description=launch.description,
        summary=resolve_interview_summary(
            title=launch.title,
            description=launch.description,
            difficulty=launch.difficulty,
            summary=launch.summary,
        ),
        interview_created_at=launch.interview_created_at,
        assignees=assignee_details,
    )
