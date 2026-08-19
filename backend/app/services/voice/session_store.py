"""In-progress interview voice session persistence in assignment submission_data."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.models.launched_interview import LaunchedInterviewUser
from backend.app.services.voice.session_config import InterviewSessionConfig


def _base_submission(assignment: LaunchedInterviewUser) -> dict[str, Any]:
    return dict(assignment.submission_data or {})


def get_pauses_used(assignment: LaunchedInterviewUser) -> int:
    data = _base_submission(assignment)
    session = data.get("voice_session") or {}
    try:
        return max(0, int(session.get("pauses_used") or 0))
    except (TypeError, ValueError):
        return 0


def get_pause_state(
    assignment: LaunchedInterviewUser,
    session_config: InterviewSessionConfig,
) -> dict[str, int]:
    used = get_pauses_used(assignment)
    max_pauses = session_config.max_pauses_per_interview
    return {
        "pauses_used": used,
        "pauses_remaining": max(0, max_pauses - used),
        "max_pauses_per_interview": max_pauses,
    }


def record_interview_pause(
    db: Session,
    assignment: LaunchedInterviewUser,
    session_config: InterviewSessionConfig,
) -> dict[str, Any]:
    data = _base_submission(assignment)
    voice_session = dict(data.get("voice_session") or {})
    used = get_pauses_used(assignment)
    max_pauses = session_config.max_pauses_per_interview
    if used >= max_pauses:
        raise ValueError("Pause limit reached for this interview")

    used += 1
    voice_session["pauses_used"] = used
    voice_session["updated_at"] = datetime.utcnow().isoformat()
    pause_log = list(voice_session.get("pause_events") or [])
    pause_log.append({"at": datetime.utcnow().isoformat()})
    voice_session["pause_events"] = pause_log[-20:]

    data["voice_session"] = voice_session
    assignment.submission_data = data
    db.commit()
    db.refresh(assignment)

    return {
        "pauses_used": used,
        "pauses_remaining": max(0, max_pauses - used),
        "max_pauses_per_interview": max_pauses,
        "pause_duration_seconds": session_config.pause_duration_seconds,
    }


def get_session_progress(assignment: LaunchedInterviewUser) -> dict[str, Any]:
    data = _base_submission(assignment)
    session = data.get("voice_session") or {}
    checkpoints = data.get("checkpoints") or []
    answers = data.get("answers") or []
    return {
        "checkpoints": checkpoints,
        "answers": answers,
        "current_question_index": session.get("current_question_index", 0),
        "voice_session": session,
    }


def save_answer_checkpoint(
    db: Session,
    assignment: LaunchedInterviewUser,
    *,
    question_id: int | None,
    question_order: int,
    question_text: str,
    transcript: str,
    audio_key: str | None = None,
    audio_url: str | None = None,
    audio_playback_key: str | None = None,
    audio_playback_url: str | None = None,
    video_key: str | None = None,
    video_url: str | None = None,
    video_playback_key: str | None = None,
    video_playback_url: str | None = None,
    duration_ms: int | None = None,
    video_duration_ms: int | None = None,
    stt_language_code: str | None = None,
    current_question_index: int | None = None,
) -> dict[str, Any]:
    data = _base_submission(assignment)
    checkpoints: list[dict[str, Any]] = list(data.get("checkpoints") or [])
    answers: list[dict[str, Any]] = list(data.get("answers") or [])

    checkpoint = {
        "question_id": question_id,
        "order": question_order,
        "question": question_text,
        "transcript": transcript,
        "answer": transcript,
        "audio_key": audio_key,
        "audio_url": audio_url,
        "audio_playback_key": audio_playback_key,
        "audio_playback_url": audio_playback_url,
        "video_key": video_key,
        "video_url": video_url,
        "video_playback_key": video_playback_key,
        "video_playback_url": video_playback_url,
        "duration_ms": duration_ms,
        "video_duration_ms": video_duration_ms,
        "stt_language_code": stt_language_code,
        "saved_at": datetime.utcnow().isoformat(),
    }

    checkpoints = [c for c in checkpoints if c.get("order") != question_order]
    checkpoints.append(checkpoint)
    checkpoints.sort(key=lambda item: item.get("order") or 0)

    answer_entry = {
        "question_id": question_id,
        "question": question_text,
        "answer": transcript,
        "audio_key": audio_key,
        "audio_url": audio_url,
        "audio_playback_key": audio_playback_key,
        "audio_playback_url": audio_playback_url,
        "video_key": video_key,
        "video_url": video_url,
        "video_playback_key": video_playback_key,
        "video_playback_url": video_playback_url,
    }
    answers = [a for a in answers if a.get("question_id") != question_id]
    answers.append(answer_entry)

    voice_session = dict(data.get("voice_session") or {})
    if current_question_index is not None:
        voice_session["current_question_index"] = current_question_index
    voice_session["updated_at"] = datetime.utcnow().isoformat()

    data["checkpoints"] = checkpoints
    data["answers"] = answers
    data["voice_session"] = voice_session
    assignment.submission_data = data
    db.commit()
    db.refresh(assignment)
    return checkpoint


def update_answer_playback_cache(
    db: Session,
    assignment: LaunchedInterviewUser,
    *,
    question_order: int,
    audio_playback_key: str | None = None,
    audio_playback_url: str | None = None,
) -> None:
    """Attach a generated playback MP3 key to an existing checkpoint/answer."""
    if not audio_playback_key:
        return

    data = deepcopy(_base_submission(assignment))
    changed = False

    checkpoints: list[dict[str, Any]] = list(data.get("checkpoints") or [])
    question_id = None
    for item in checkpoints:
        if int(item.get("order") or 0) == int(question_order):
            item["audio_playback_key"] = audio_playback_key
            if audio_playback_url:
                item["audio_playback_url"] = audio_playback_url
            question_id = item.get("question_id")
            changed = True
            break

    answers: list[dict[str, Any]] = list(data.get("answers") or [])
    for item in answers:
        matched = False
        if question_id is not None and item.get("question_id") == question_id:
            matched = True
        elif int(item.get("order") or 0) == int(question_order):
            matched = True
        if matched:
            item["audio_playback_key"] = audio_playback_key
            if audio_playback_url:
                item["audio_playback_url"] = audio_playback_url
            changed = True

    if not changed:
        return

    data["checkpoints"] = checkpoints
    data["answers"] = answers
    assignment.submission_data = data
    flag_modified(assignment, "submission_data")
    db.commit()
    db.refresh(assignment)
