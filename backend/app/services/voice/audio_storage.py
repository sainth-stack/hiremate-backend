"""Persist interview answer audio to S3."""
from __future__ import annotations

import uuid
from datetime import datetime

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from backend.app.services.s3_service import _get_s3_client, generate_presigned_url

logger = get_logger("services.voice.audio")

INTERVIEW_AUDIO_PREFIX = "interview-recordings"
AUDIO_CONTENT_TYPES = {
    "webm": "audio/webm",
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
}


def guess_audio_content_type(key: str | None) -> str:
    if not key:
        return "audio/webm"
    ext = key.rsplit(".", 1)[-1].lower()
    return AUDIO_CONTENT_TYPES.get(ext, "audio/webm")


def get_presigned_audio_url(key: str, expiration: int | None = None) -> str:
    url = generate_presigned_url(key, expiration=expiration)
    if not url:
        raise RuntimeError("Could not generate audio playback URL")
    return url

INTERVIEW_AUDIO_PREFIX = "interview-recordings"


def build_answer_audio_key(
    *,
    user_id: int,
    interview_id: int,
    assignment_id: int,
    question_order: int,
    extension: str = "webm",
) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return (
        f"{INTERVIEW_AUDIO_PREFIX}/{user_id}/{interview_id}/"
        f"{assignment_id}/q{question_order}_{stamp}_{suffix}.{extension.lstrip('.')}"
    )


def upload_interview_answer_audio(
    *,
    audio_bytes: bytes,
    user_id: int,
    interview_id: int,
    assignment_id: int,
    question_order: int,
    mime_type: str = "audio/webm",
) -> dict[str, str]:
    extension = "webm"
    if "wav" in mime_type:
        extension = "wav"
    elif "mp3" in mime_type or "mpeg" in mime_type:
        extension = "mp3"
    elif "ogg" in mime_type:
        extension = "ogg"

    key = build_answer_audio_key(
        user_id=user_id,
        interview_id=interview_id,
        assignment_id=assignment_id,
        question_order=question_order,
        extension=extension,
    )

    s3 = _get_s3_client()
    s3.put_object(
        Bucket=settings.aws_bucket_name,
        Key=key,
        Body=audio_bytes,
        ContentType=mime_type,
    )
    url = f"https://{settings.aws_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{key}"
    logger.info("Interview audio uploaded key=%s size=%d", key, len(audio_bytes))
    presigned_url = generate_presigned_url(key)
    return {
        "key": key,
        "url": url,
        "presigned_url": presigned_url,
    }
