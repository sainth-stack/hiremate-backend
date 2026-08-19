"""Lookup stored interview answer media metadata."""
from __future__ import annotations

from typing import Any

from backend.app.services.voice.media_storage import guess_audio_content_type, guess_video_content_type


def _iter_answer_records(submission_data: dict | None) -> list[dict[str, Any]]:
    if not submission_data or not isinstance(submission_data, dict):
        return []

    records: list[dict[str, Any]] = []
    for source_key in ("answers", "checkpoints"):
        items = submission_data.get(source_key) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                records.append(item)
    return records


def _matches_order(item: dict[str, Any], *, order: int | None, question_id: int | None) -> bool:
    item_order = item.get("order")
    item_question_id = item.get("question_id")
    if order is not None and item_order is not None and int(item_order) == int(order):
        return True
    if question_id is not None and item_question_id is not None and int(item_question_id) == int(question_id):
        return True
    return False


def find_answer_media(
    submission_data: dict | None,
    *,
    order: int | None = None,
    question_id: int | None = None,
) -> dict[str, Any] | None:
    """Find answer record with audio and/or video for a question."""
    for item in _iter_answer_records(submission_data):
        if not (item.get("audio_key") or item.get("video_key")):
            continue
        if _matches_order(item, order=order, question_id=question_id):
            return item

    if order is not None:
        for index, item in enumerate(_iter_answer_records(submission_data), start=1):
            if index == int(order) and (item.get("audio_key") or item.get("video_key")):
                return item
    return None


def find_answer_audio(
    submission_data: dict | None,
    *,
    order: int | None = None,
    question_id: int | None = None,
) -> dict[str, Any] | None:
    item = find_answer_media(submission_data, order=order, question_id=question_id)
    if item and item.get("audio_key"):
        return item
    return None


def resolve_stream_key(item: dict[str, Any], *, kind: str) -> tuple[str | None, str]:
    if kind == "video":
        playback = item.get("video_playback_key")
        source = item.get("video_key")
        key = playback or source
        if playback:
            return key, "video/mp4"
        return key, guess_video_content_type(source)
    playback = item.get("audio_playback_key")
    source = item.get("audio_key")
    key = playback or source
    if playback:
        return key, "audio/mpeg"
    return key, guess_audio_content_type(source)


def media_filename(order: int, kind: str, content_type: str) -> str:
    if "mp4" in content_type:
        ext = "mp4"
    elif "mpeg" in content_type or "mp3" in content_type:
        ext = "mp3"
    elif kind == "video":
        ext = "webm"
    else:
        ext = "webm"
    return f"interview_q{order}_{kind}.{ext}"


def list_answer_audio_items(submission_data: dict | None) -> list[dict[str, Any]]:
    """Return deduplicated answer records that include audio, ordered by question order."""
    seen_orders: set[int] = set()
    results: list[dict[str, Any]] = []

    for item in _iter_answer_records(submission_data):
        if not item.get("audio_key"):
            continue
        order_val = item.get("order")
        order = int(order_val) if order_val is not None else len(results) + 1
        if order in seen_orders:
            continue
        seen_orders.add(order)
        results.append({**item, "order": order})

    results.sort(key=lambda row: row.get("order") or 0)
    return results
