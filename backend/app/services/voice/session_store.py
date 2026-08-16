"""In-progress interview voice session persistence in assignment submission_data."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.launched_interview import LaunchedInterviewUser


def _base_submission(assignment: LaunchedInterviewUser) -> dict[str, Any]:
    return dict(assignment.submission_data or {})


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
    duration_ms: int | None = None,
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
        "duration_ms": duration_ms,
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
