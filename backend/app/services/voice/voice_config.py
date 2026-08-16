"""Resolve TTS voice configuration for a launched interview assignment."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.launched_interview import LaunchedInterview
from backend.app.services.interview_assignment import get_user_assignment
from backend.app.services.voice.cartesia_service import (
    cartesia_language_for_voice,
    custom_voice_storage_id,
    get_default_cartesia_voice,
    is_custom_voice_storage_id,
    normalize_cartesia_voice_id,
    synthesize_cartesia_speech,
)
from backend.app.services.voice.custom_voice_service import (
    allowed_custom_voice_ids,
    get_active_custom_voice_by_cartesia_id,
)


@dataclass
class LaunchVoiceConfig:
    provider: str
    voice_id: str
    voice_label: str
    language_code: str
    cartesia_language: str = "en"

    @property
    def display_name(self) -> str:
        return self.voice_label or self.voice_id


def _custom_language_map(db: Session) -> dict[str, str]:
    from backend.app.services.voice.custom_voice_service import list_active_custom_voices

    return {voice.cartesia_voice_id: voice.cartesia_language for voice in list_active_custom_voices(db)}


def default_launch_voice() -> LaunchVoiceConfig:
    featured = get_default_cartesia_voice()
    return LaunchVoiceConfig(
        provider="cartesia",
        voice_id=featured["id"],
        voice_label=str(featured["label"]),
        language_code=settings.sarvam_default_language,
        cartesia_language=str(featured.get("cartesia_language") or "en"),
    )


def resolve_launch_voice_config(db: Session, launch: LaunchedInterview | None) -> LaunchVoiceConfig:
    if not launch or not launch.voice_id:
        return default_launch_voice()

    allowed_custom = allowed_custom_voice_ids(db)
    custom_languages = _custom_language_map(db)
    stored_voice_id = launch.voice_id.strip()
    cartesia_uuid = normalize_cartesia_voice_id(stored_voice_id, allowed_custom_ids=allowed_custom)

    if is_custom_voice_storage_id(stored_voice_id) or cartesia_uuid in allowed_custom:
        custom_voice = get_active_custom_voice_by_cartesia_id(db, cartesia_uuid)
        return LaunchVoiceConfig(
            provider="cartesia",
            voice_id=custom_voice_storage_id(cartesia_uuid),
            voice_label=str(launch.voice_label or (custom_voice.name if custom_voice else cartesia_uuid)),
            language_code=str(
                launch.tts_language_code
                or (custom_voice.tts_language_code if custom_voice else settings.sarvam_default_language)
            ),
            cartesia_language=str(
                custom_voice.cartesia_language if custom_voice else custom_languages.get(cartesia_uuid, "en")
            ),
        )

    from backend.app.services.voice.cartesia_service import CARTESIA_PREMIUM_INDIAN_VOICES

    catalog = {voice["id"]: voice for voice in CARTESIA_PREMIUM_INDIAN_VOICES}
    matched = catalog.get(cartesia_uuid) or get_default_cartesia_voice()
    return LaunchVoiceConfig(
        provider="cartesia",
        voice_id=cartesia_uuid,
        voice_label=str(launch.voice_label or matched.get("label") or cartesia_uuid),
        language_code=str(launch.tts_language_code or settings.sarvam_default_language),
        cartesia_language=str(matched.get("cartesia_language") or "en"),
    )


def resolve_assignment_voice_config(
    db: Session,
    user_id: int,
    interview_id: int,
) -> LaunchVoiceConfig:
    _assignment, launch = get_user_assignment(db, user_id, interview_id)
    return resolve_launch_voice_config(db, launch)


def resolve_question_count(interview, launch) -> int:
    if launch and launch.question_count:
        return int(launch.question_count)
    if interview and interview.question_count:
        return int(interview.question_count)
    return 15


def synthesize_launch_speech(*, text: str, voice: LaunchVoiceConfig, db: Session | None = None) -> bytes:
    """Interview TTS always uses Cartesia. Sarvam is STT-only."""
    allowed_custom = allowed_custom_voice_ids(db) if db is not None else None
    cartesia_uuid = normalize_cartesia_voice_id(voice.voice_id, allowed_custom_ids=allowed_custom)
    custom_languages = _custom_language_map(db) if db is not None else None
    language = voice.cartesia_language or cartesia_language_for_voice(
        cartesia_uuid,
        custom_languages=custom_languages,
    )
    return synthesize_cartesia_speech(
        text=text,
        voice_id=voice.voice_id,
        language=language,
        allowed_custom_ids=allowed_custom,
    )
