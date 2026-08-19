"""Persist interview answer audio/video to S3 with optional playback transcodes."""
from __future__ import annotations

import uuid
from datetime import datetime

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from backend.app.services.s3_service import generate_presigned_url, get_s3_object, upload_bytes_to_s3
from backend.app.services.voice.media_transcode import transcode_audio_to_mp3, transcode_video_to_mp4

logger = get_logger("services.voice.media")

INTERVIEW_MEDIA_PREFIX = "interview-recordings"

CONTENT_TYPES = {
    "webm": "audio/webm",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "mp4": "video/mp4",
}

WEBM_EBML_MAGIC = b"\x1a\x45\xdf\xa3"
MP4_FTYP_MAGIC = b"ftyp"


class UnplayableMediaError(RuntimeError):
    """Raised when stored media bytes cannot be decoded for browser playback."""


def guess_content_type(key: str | None, *, default: str = "application/octet-stream") -> str:
    if not key:
        return default
    ext = key.rsplit(".", 1)[-1].lower()
    return CONTENT_TYPES.get(ext, default)


def guess_audio_content_type(key: str | None) -> str:
    return guess_content_type(key, default="audio/webm")


def guess_video_content_type(key: str | None) -> str:
    return guess_content_type(key, default="video/webm")


def build_media_key(
    *,
    user_id: int,
    interview_id: int,
    assignment_id: int,
    question_order: int,
    suffix: str,
    extension: str,
) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    token = uuid.uuid4().hex[:8]
    ext = extension.lstrip(".")
    return (
        f"{INTERVIEW_MEDIA_PREFIX}/{user_id}/{interview_id}/"
        f"{assignment_id}/q{question_order}_{suffix}_{stamp}_{token}.{ext}"
    )


def get_presigned_media_url(
    key: str,
    *,
    expiration: int | None = None,
    download: bool = False,
    filename: str | None = None,
    content_type: str | None = None,
) -> str:
    disposition = None
    if download and filename:
        disposition = f'attachment; filename="{filename}"'
    url = generate_presigned_url(
        key,
        expiration=expiration,
        response_content_type=content_type,
        response_content_disposition=disposition,
    )
    if not url:
        raise RuntimeError("Could not generate media URL")
    return url


def _extension_from_mime(mime_type: str, default: str = "webm") -> str:
    mime = (mime_type or "").lower()
    if "mp3" in mime or "mpeg" in mime:
        return "mp3"
    if "wav" in mime:
        return "wav"
    if "ogg" in mime:
        return "ogg"
    if "mp4" in mime:
        return "mp4"
    if "webm" in mime:
        return "webm"
    return default


def _key_extension(key: str | None) -> str:
    if not key or "." not in key:
        return "webm"
    return key.rsplit(".", 1)[-1].lower()


def detect_media_format(raw_bytes: bytes, *, kind: str) -> str | None:
    """Return a coarse format label when bytes look like a known container."""
    if not raw_bytes or len(raw_bytes) < 4:
        return None
    if raw_bytes[:4] == WEBM_EBML_MAGIC:
        return "webm"
    if raw_bytes[:3] == b"ID3" or raw_bytes[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if raw_bytes[:4] == b"RIFF":
        return "wav"
    if raw_bytes[:4] == b"OggS":
        return "ogg"
    if kind == "video" and MP4_FTYP_MAGIC in raw_bytes[:32]:
        return "mp4"
    return None


def is_playable_media(raw_bytes: bytes, *, kind: str) -> bool:
    return detect_media_format(raw_bytes, kind=kind) is not None


def cache_playback_mp3(
    *,
    mp3_bytes: bytes,
    user_id: int,
    interview_id: int,
    assignment_id: int,
    question_order: int,
    suffix: str = "audio_playback",
) -> dict[str, str]:
    """Persist a generated MP3 playback file and return its storage metadata."""
    playback_key = build_media_key(
        user_id=user_id,
        interview_id=interview_id,
        assignment_id=assignment_id,
        question_order=question_order,
        suffix=suffix,
        extension="mp3",
    )
    upload_bytes_to_s3(playback_key, mp3_bytes, "audio/mpeg")
    playback_url = (
        f"https://{settings.aws_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{playback_key}"
    )
    return {
        "playback_key": playback_key,
        "playback_url": playback_url,
        "presigned_url": generate_presigned_url(playback_key, response_content_type="audio/mpeg"),
    }


def load_stream_bytes(
    key: str,
    *,
    kind: str,
    content_type: str | None = None,
) -> tuple[bytes, str]:
    """Load media from S3 and return browser-friendly bytes + MIME type."""
    obj = get_s3_object(key)
    raw_bytes = obj["Body"].read()
    if not raw_bytes:
        raise RuntimeError("Media file is empty")

    s3_type = (obj.get("ContentType") or content_type or "").split(";")[0].strip().lower()
    ext = _key_extension(key)

    if kind == "audio":
        if ext == "mp3" or s3_type == "audio/mpeg" or detect_media_format(raw_bytes, kind=kind) == "mp3":
            return raw_bytes, "audio/mpeg"
        mp3_bytes = transcode_audio_to_mp3(raw_bytes, input_suffix=ext)
        if mp3_bytes:
            return mp3_bytes, "audio/mpeg"
        if detect_media_format(raw_bytes, kind=kind) == "webm":
            return raw_bytes, "audio/webm"
        raise UnplayableMediaError("Recording file is corrupted or unsupported")

    if kind == "video":
        if ext == "mp4" or s3_type == "video/mp4" or detect_media_format(raw_bytes, kind=kind) == "mp4":
            return raw_bytes, "video/mp4"
        mp4_bytes = transcode_video_to_mp4(raw_bytes, input_suffix=ext)
        if mp4_bytes:
            return mp4_bytes, "video/mp4"
        if detect_media_format(raw_bytes, kind=kind) == "webm":
            return raw_bytes, "video/webm"
        raise UnplayableMediaError("Recording file is corrupted or unsupported")

    return raw_bytes, s3_type or "application/octet-stream"


def upload_interview_answer_audio(
    *,
    audio_bytes: bytes,
    user_id: int,
    interview_id: int,
    assignment_id: int,
    question_order: int,
    mime_type: str = "audio/webm",
) -> dict[str, str | None]:
    extension = _extension_from_mime(mime_type, "webm")
    source_key = build_media_key(
        user_id=user_id,
        interview_id=interview_id,
        assignment_id=assignment_id,
        question_order=question_order,
        suffix="audio",
        extension=extension,
    )
    upload_bytes_to_s3(source_key, audio_bytes, mime_type)

    playback_key = None
    playback_url = None
    mp3_bytes = transcode_audio_to_mp3(audio_bytes, input_suffix=extension)
    if mp3_bytes:
        playback_key = build_media_key(
            user_id=user_id,
            interview_id=interview_id,
            assignment_id=assignment_id,
            question_order=question_order,
            suffix="audio_playback",
            extension="mp3",
        )
        upload_bytes_to_s3(playback_key, mp3_bytes, "audio/mpeg")
        playback_url = f"https://{settings.aws_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{playback_key}"
        logger.info("Interview audio playback mp3 uploaded key=%s", playback_key)
    else:
        logger.info("Interview audio stored without mp3 transcode key=%s", source_key)

    source_url = f"https://{settings.aws_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{source_key}"
    playback_for_url = playback_key or source_key
    return {
        "key": source_key,
        "url": source_url,
        "playback_key": playback_key,
        "playback_url": playback_url,
        "presigned_url": generate_presigned_url(playback_for_url, response_content_type="audio/mpeg" if playback_key else mime_type),
    }


def upload_interview_answer_video(
    *,
    video_bytes: bytes,
    user_id: int,
    interview_id: int,
    assignment_id: int,
    question_order: int,
    mime_type: str = "video/webm",
) -> dict[str, str | None]:
    extension = _extension_from_mime(mime_type, "webm")
    source_key = build_media_key(
        user_id=user_id,
        interview_id=interview_id,
        assignment_id=assignment_id,
        question_order=question_order,
        suffix="video",
        extension=extension,
    )
    upload_bytes_to_s3(source_key, video_bytes, mime_type)

    playback_key = None
    playback_url = None
    mp4_bytes = transcode_video_to_mp4(video_bytes, input_suffix=extension)
    if mp4_bytes:
        playback_key = build_media_key(
            user_id=user_id,
            interview_id=interview_id,
            assignment_id=assignment_id,
            question_order=question_order,
            suffix="video_playback",
            extension="mp4",
        )
        upload_bytes_to_s3(playback_key, mp4_bytes, "video/mp4")
        playback_url = f"https://{settings.aws_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{playback_key}"
        logger.info("Interview video playback mp4 uploaded key=%s", playback_key)
    else:
        logger.info("Interview video stored without mp4 transcode key=%s", source_key)

    source_url = f"https://{settings.aws_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{source_key}"
    return {
        "key": source_key,
        "url": source_url,
        "playback_key": playback_key,
        "playback_url": playback_url,
        "presigned_url": generate_presigned_url(playback_key or source_key),
    }
