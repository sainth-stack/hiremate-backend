"""Sarvam AI TTS and STT integration."""
from __future__ import annotations

import base64
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger

logger = get_logger("services.sarvam")

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"

ALLOWED_STT_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/webm",
    "video/webm",
    "audio/ogg",
    "audio/opus",
    "audio/flac",
    "audio/mp4",
    "audio/x-m4a",
    "application/octet-stream",
}


def _headers() -> dict[str, str]:
    if not settings.sarvam_api_key:
        raise RuntimeError("SARVAM_API_KEY is not configured")
    return {"api-subscription-key": settings.sarvam_api_key}


def _normalize_stt_model(model: str | None) -> str:
    raw = (model or settings.sarvam_stt_model or "saaras:v3").strip()
    if raw.startswith("saaras:v3"):
        return "saaras:v3"
    if raw.startswith("saaras:v4"):
        return "saaras:v4"
    if raw.startswith("saarika:"):
        return raw
    return raw


def normalize_stt_content_type(content_type: str | None, filename: str | None = None) -> str:
    """Sarvam rejects values like audio/webm;codecs=opus — normalize to a supported MIME type."""
    raw = (content_type or "").split(";")[0].strip().lower()
    if raw in ALLOWED_STT_CONTENT_TYPES:
        return raw

    name = (filename or "").lower()
    if name.endswith(".webm"):
        return "audio/webm"
    if name.endswith(".mp3"):
        return "audio/mpeg"
    if name.endswith(".wav"):
        return "audio/wav"
    if name.endswith(".ogg"):
        return "audio/ogg"
    if name.endswith(".m4a") or name.endswith(".mp4"):
        return "audio/mp4"
    return "audio/webm"


def normalize_stt_language_code(language_code: str | None) -> str:
    lang = (language_code or settings.sarvam_default_language or "en-IN").strip()
    if not lang or lang.lower() == "unknown":
        return "unknown"
    if lang in {
        "hi-IN", "bn-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN",
        "en-IN", "gu-IN", "as-IN", "ur-IN", "ne-IN", "kok-IN", "ks-IN", "sd-IN", "sa-IN",
        "sat-IN", "mni-IN", "brx-IN", "mai-IN", "doi-IN", "unknown",
    }:
        return lang
    if lang.lower().startswith("en"):
        return "en-IN"
    if lang.lower().startswith("hi"):
        return "hi-IN"
    return "unknown"


def synthesize_speech(
    *,
    text: str,
    speaker: str | None = None,
    language_code: str | None = None,
) -> bytes:
    """Convert text to MP3 audio bytes via Sarvam Bulbul TTS."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("text is required for TTS")

    payload: dict[str, Any] = {
        "text": cleaned,
        "language_code": language_code or settings.sarvam_default_language,
        "speaker": (speaker or settings.sarvam_default_speaker).lower(),
        "model": settings.sarvam_tts_model,
        "output_audio_codec": "mp3",
        "speech_sample_rate": 24000,
        "pace": 1.0,
    }

    with httpx.Client(timeout=settings.http_request_timeout) as client:
        response = client.post(
            SARVAM_TTS_URL,
            headers={**_headers(), "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    audios = data.get("audios") or []
    if not audios:
        raise RuntimeError("Sarvam TTS returned no audio")

    return base64.b64decode(audios[0])


def transcribe_audio(
    *,
    audio_bytes: bytes,
    filename: str,
    content_type: str = "audio/webm",
    language_code: str | None = None,
    client_transcript: str | None = None,
) -> dict[str, Any]:
    """Transcribe audio via Sarvam REST STT."""
    if not audio_bytes:
        raise ValueError("audio file is empty")

    model = _normalize_stt_model(settings.sarvam_stt_model)
    normalized_type = normalize_stt_content_type(content_type, filename)
    normalized_lang = normalize_stt_language_code(language_code)

    form_data: dict[str, str] = {
        "model": model,
        "mode": "transcribe",
    }
    if normalized_lang != "unknown":
        form_data["language_code"] = normalized_lang

    upload_name = filename or "answer.webm"
    if normalized_type == "audio/webm" and not upload_name.lower().endswith(".webm"):
        upload_name = f"{upload_name.rsplit('.', 1)[0]}.webm"

    files = {
        "file": (upload_name, audio_bytes, normalized_type),
    }

    with httpx.Client(timeout=max(settings.http_request_timeout, 60)) as client:
        response = client.post(
            SARVAM_STT_URL,
            headers=_headers(),
            data=form_data,
            files=files,
        )
        if response.status_code >= 400:
            logger.error(
                "Sarvam STT failed (%s): type=%s lang=%s body=%s",
                response.status_code,
                normalized_type,
                normalized_lang,
                response.text[:500],
            )
        response.raise_for_status()
        data = response.json()

    transcript = str(data.get("transcript") or "").strip()
    fallback = str(client_transcript or "").strip()
    if not transcript and fallback:
        transcript = fallback
    if not transcript:
        raise RuntimeError("Could not transcribe audio — please speak clearly and try again")

    return {
        "transcript": transcript,
        "language_code": data.get("language_code") or normalized_lang,
        "language_probability": data.get("language_probability"),
        "request_id": data.get("request_id"),
    }
