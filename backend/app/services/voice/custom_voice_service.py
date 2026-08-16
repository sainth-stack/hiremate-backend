"""Persist and resolve admin-created Cartesia voice clones."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.custom_voice_clone import CustomVoiceClone
from backend.app.services.voice.cartesia_service import (
    CARTESIA_PREMIUM_INDIAN_VOICES,
    clone_cartesia_voice,
    custom_voice_storage_id,
    delete_cartesia_voice,
    is_valid_cartesia_uuid,
)


def list_active_custom_voices(db: Session) -> list[CustomVoiceClone]:
    return (
        db.query(CustomVoiceClone)
        .filter(CustomVoiceClone.deleted_at.is_(None))
        .order_by(CustomVoiceClone.created_at.desc())
        .all()
    )


def get_active_custom_voice_by_cartesia_id(db: Session, cartesia_voice_id: str) -> CustomVoiceClone | None:
    return (
        db.query(CustomVoiceClone)
        .filter(
            CustomVoiceClone.cartesia_voice_id == cartesia_voice_id,
            CustomVoiceClone.deleted_at.is_(None),
        )
        .first()
    )


def get_active_custom_voice_by_storage_id(db: Session, voice_id: str) -> CustomVoiceClone | None:
    from backend.app.services.voice.cartesia_service import extract_cartesia_uuid

    cartesia_id = extract_cartesia_uuid(voice_id)
    if not is_valid_cartesia_uuid(cartesia_id):
        return None
    return get_active_custom_voice_by_cartesia_id(db, cartesia_id)


def allowed_custom_voice_ids(db: Session) -> set[str]:
    return {voice.cartesia_voice_id for voice in list_active_custom_voices(db)}


def custom_voice_to_option(voice: CustomVoiceClone) -> dict[str, Any]:
    return {
        "id": custom_voice_storage_id(voice.cartesia_voice_id),
        "label": voice.name,
        "provider": "cartesia",
        "tier": "cartesia_custom",
        "language": voice.tts_language_code,
        "cartesia_language": voice.cartesia_language,
        "description": voice.description or "Custom cloned interviewer voice",
        "featured": False,
        "clone_record_id": voice.id,
    }


def create_custom_voice_clone(
    db: Session,
    *,
    clip_bytes: bytes,
    filename: str,
    name: str,
    cartesia_language: str,
    tts_language_code: str = "en-IN",
    description: str | None = None,
    created_by_user_id: int | None = None,
    base_voice_id: str | None = None,
) -> CustomVoiceClone:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("Voice name is required")

    base_id = base_voice_id or CARTESIA_PREMIUM_INDIAN_VOICES[0]["id"]
    cloned = clone_cartesia_voice(
        clip_bytes=clip_bytes,
        filename=filename,
        name=cleaned_name,
        language=cartesia_language,
        description=description,
        base_voice_id=base_id,
    )

    record = CustomVoiceClone(
        cartesia_voice_id=str(cloned["id"]),
        name=cleaned_name,
        description=(description or "").strip() or None,
        cartesia_language=cartesia_language,
        tts_language_code=tts_language_code,
        source_filename=filename or None,
        created_by_user_id=created_by_user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def soft_delete_custom_voice_clone(db: Session, clone_id: int) -> CustomVoiceClone | None:
    record = (
        db.query(CustomVoiceClone)
        .filter(CustomVoiceClone.id == clone_id, CustomVoiceClone.deleted_at.is_(None))
        .first()
    )
    if not record:
        return None

    try:
        delete_cartesia_voice(record.cartesia_voice_id)
    except Exception:
        # Keep local soft-delete even if Cartesia cleanup fails.
        pass

    record.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record
