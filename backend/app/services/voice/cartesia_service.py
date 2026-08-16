"""Cartesia TTS integration and curated Indian voice catalog."""
from __future__ import annotations

import re
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger

logger = get_logger("services.cartesia")

CARTESIA_VOICES_URL = "https://api.cartesia.ai/voices"
CARTESIA_TTS_BYTES_URL = "https://api.cartesia.ai/tts/bytes"
CARTESIA_VOICES_CLONE_URL = "https://api.cartesia.ai/voices/clone"

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Curated Cartesia Premium voices for Indian interviews (public catalog UUIDs).
CARTESIA_PREMIUM_INDIAN_VOICES: list[dict[str, Any]] = [
    {
        "id": "07bc462a-c644-49f1-baf7-82d5599131be",
        "label": "Sindhu",
        "provider": "cartesia",
        "tier": "cartesia_premium",
        "language": "en-IN",
        "cartesia_language": "en",
        "description": "Warm conversational Indian tone — great for friendly interviews",
        "featured": True,
    },
    {
        "id": "76961778-5ce4-4aa9-9cdf-66a029d61a8f",
        "label": "Bhavana",
        "provider": "cartesia",
        "tier": "cartesia_premium",
        "language": "en-IN",
        "cartesia_language": "hi",
        "description": "Reassuring Indian voice — calm and professional",
        "featured": False,
    },
    {
        "id": "3b554273-4299-48b9-9aaf-eefd438e3941",
        "label": "Simi",
        "provider": "cartesia",
        "tier": "cartesia_premium",
        "language": "en-IN",
        "cartesia_language": "en",
        "description": "Clear support-style Indian English — easy to understand",
        "featured": False,
    },
    {
        "id": "1259b7e3-cb8a-43df-9446-30971a46b8b0",
        "label": "Devansh",
        "provider": "cartesia",
        "tier": "cartesia_premium",
        "language": "en-IN",
        "cartesia_language": "en",
        "description": "Professional warm male voice — confident interviewer style",
        "featured": False,
    },
]

_VOICE_BY_ID = {voice["id"]: voice for voice in CARTESIA_PREMIUM_INDIAN_VOICES}

CLONE_ALLOWED_EXTENSIONS = {
    ".flac",
    ".mp3",
    ".mpeg",
    ".mpga",
    ".oga",
    ".ogg",
    ".wav",
    ".webm",
}


def _headers(*, json: bool = True) -> dict[str, str]:
    if not settings.cartesia_api_key:
        raise RuntimeError("CARTESIA_API_KEY is not configured")
    headers = {
        "Authorization": f"Bearer {settings.cartesia_api_key}",
        "Cartesia-Version": settings.cartesia_api_version,
    }
    if json:
        headers["Content-Type"] = "application/json"
    return headers


def is_valid_cartesia_uuid(value: str | None) -> bool:
    return bool(value and UUID_RE.match(value.strip()))


def is_custom_voice_storage_id(voice_id: str | None) -> bool:
    return (voice_id or "").strip().startswith("custom:")


def custom_voice_storage_id(cartesia_voice_id: str) -> str:
    return f"custom:{cartesia_voice_id.strip()}"


def extract_cartesia_uuid(voice_id: str | None) -> str:
    cleaned = (voice_id or "").strip()
    if cleaned.startswith("custom:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    return cleaned


def normalize_cartesia_voice_id(
    voice_id: str | None,
    *,
    allowed_custom_ids: set[str] | None = None,
) -> str:
    """Return a Cartesia voice UUID suitable for TTS API calls."""
    original = (voice_id or "").strip()
    cleaned = extract_cartesia_uuid(original)

    if cleaned in _VOICE_BY_ID:
        return cleaned

    if is_valid_cartesia_uuid(cleaned):
        if original.startswith("custom:"):
            return cleaned
        if allowed_custom_ids and cleaned in allowed_custom_ids:
            return cleaned

    featured = extract_cartesia_uuid(settings.featured_cartesia_voice_id)
    if featured in _VOICE_BY_ID:
        return featured

    return CARTESIA_PREMIUM_INDIAN_VOICES[0]["id"]


def resolve_voice_storage_id(
    voice_id: str | None,
    *,
    allowed_custom_ids: set[str] | None = None,
    custom_labels: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Return (storage voice_id, display label)."""
    default = get_default_cartesia_voice()
    original = (voice_id or "").strip()
    if not original:
        return default["id"], str(default["label"])

    cartesia_uuid = normalize_cartesia_voice_id(original, allowed_custom_ids=allowed_custom_ids)
    if original.startswith("custom:") and cartesia_uuid == extract_cartesia_uuid(original):
        label = (custom_labels or {}).get(cartesia_uuid) or cartesia_uuid
        return custom_voice_storage_id(cartesia_uuid), label

    if cartesia_uuid in _VOICE_BY_ID:
        return cartesia_uuid, str(_VOICE_BY_ID[cartesia_uuid]["label"])

    return default["id"], str(default["label"])


def cartesia_language_for_voice(
    voice_id: str,
    *,
    custom_languages: dict[str, str] | None = None,
) -> str:
    cartesia_uuid = normalize_cartesia_voice_id(voice_id)
    voice = _VOICE_BY_ID.get(cartesia_uuid)
    if voice:
        return str(voice.get("cartesia_language") or "en")
    if custom_languages and cartesia_uuid in custom_languages:
        return custom_languages[cartesia_uuid]
    return "en"


def get_default_cartesia_voice() -> dict[str, Any]:
    default_id = normalize_cartesia_voice_id(settings.featured_cartesia_voice_id)
    voice = _VOICE_BY_ID.get(default_id) or CARTESIA_PREMIUM_INDIAN_VOICES[0]
    return dict(voice)


def get_grouped_interview_voices(
    custom_voices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build voice catalog for admin launch UI."""
    from backend.app.services.voice.constants import SARVAM_LANGUAGE_CODES

    premium = [dict(voice) for voice in CARTESIA_PREMIUM_INDIAN_VOICES]
    default_voice = get_default_cartesia_voice()
    for item in premium:
        item["featured"] = item["id"] == default_voice["id"]

    groups: list[dict[str, Any]] = [
        {
            "tier": "cartesia_premium",
            "label": "Cartesia Premium — Indian Voices",
            "voices": premium,
        },
    ]

    clone_options = list(custom_voices or [])
    if clone_options:
        groups.insert(
            0,
            {
                "tier": "cartesia_custom",
                "label": "Custom Cloned Voices",
                "voices": clone_options,
            },
        )

    return {
        "groups": groups,
        "languages": [lang for lang in SARVAM_LANGUAGE_CODES if lang["code"] == "en-IN"],
        "default_voice": default_voice,
        "default_language": "en-IN",
    }


def clone_cartesia_voice(
    *,
    clip_bytes: bytes,
    filename: str,
    name: str,
    language: str,
    description: str | None = None,
    base_voice_id: str | None = None,
) -> dict[str, Any]:
    if not clip_bytes:
        raise ValueError("Audio clip is required to clone a voice")

    data: dict[str, str] = {
        "name": name.strip(),
        "language": language.strip(),
    }
    if description:
        data["description"] = description.strip()
    if base_voice_id:
        data["base_voice_id"] = base_voice_id

    files = {
        "clip": (filename or "clip.wav", clip_bytes, "application/octet-stream"),
    }

    with httpx.Client(timeout=max(settings.http_request_timeout, 120)) as client:
        response = client.post(
            CARTESIA_VOICES_CLONE_URL,
            headers=_headers(json=False),
            data=data,
            files=files,
        )
        if response.status_code >= 400:
            logger.error(
                "Cartesia clone failed (%s): name=%s language=%s body=%s",
                response.status_code,
                name,
                language,
                response.text[:500],
            )
        response.raise_for_status()
        payload = response.json()

    voice_id = str(payload.get("id") or "").strip()
    if not is_valid_cartesia_uuid(voice_id):
        raise RuntimeError("Cartesia clone did not return a valid voice ID")
    return payload


def delete_cartesia_voice(voice_id: str) -> None:
    cartesia_uuid = extract_cartesia_uuid(voice_id)
    if not is_valid_cartesia_uuid(cartesia_uuid):
        raise ValueError("Invalid Cartesia voice ID")

    with httpx.Client(timeout=max(settings.http_request_timeout, 30)) as client:
        response = client.delete(
            f"{CARTESIA_VOICES_URL}/{cartesia_uuid}",
            headers=_headers(json=False),
        )
        if response.status_code >= 400 and response.status_code != 404:
            logger.error(
                "Cartesia delete voice failed (%s): voice=%s body=%s",
                response.status_code,
                cartesia_uuid,
                response.text[:300],
            )
            response.raise_for_status()


def synthesize_cartesia_speech(
    *,
    text: str,
    voice_id: str,
    language: str | None = None,
    allowed_custom_ids: set[str] | None = None,
) -> bytes:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("text is required for TTS")

    resolved_voice_id = normalize_cartesia_voice_id(voice_id, allowed_custom_ids=allowed_custom_ids)
    tts_language = language or cartesia_language_for_voice(resolved_voice_id)

    payload = {
        "model_id": settings.cartesia_model_id,
        "transcript": cleaned,
        "voice": {"mode": "id", "id": resolved_voice_id},
        "language": tts_language,
        "output_format": {
            "container": "mp3",
            "sample_rate": 44100,
            "bit_rate": 128000,
        },
    }

    with httpx.Client(timeout=max(settings.http_request_timeout, 45)) as client:
        response = client.post(CARTESIA_TTS_BYTES_URL, headers=_headers(), json=payload)
        if response.status_code >= 400:
            logger.error(
                "Cartesia TTS failed (%s): voice=%s model=%s body=%s",
                response.status_code,
                resolved_voice_id,
                settings.cartesia_model_id,
                response.text[:300],
            )
        response.raise_for_status()
        content = response.content

    if not content:
        raise RuntimeError("Cartesia TTS returned empty audio")
    return content
