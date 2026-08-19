"""Backward-compatible re-exports — prefer media_storage for new code."""
from backend.app.services.voice.media_storage import (  # noqa: F401
    build_media_key as build_answer_audio_key,
    get_presigned_media_url as get_presigned_audio_url,
    guess_audio_content_type,
    guess_content_type,
    upload_interview_answer_audio,
    upload_interview_answer_video,
)

INTERVIEW_AUDIO_PREFIX = "interview-recordings"
AUDIO_CONTENT_TYPES = {
    "webm": "audio/webm",
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
}
