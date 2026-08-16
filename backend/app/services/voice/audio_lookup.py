"""Lookup stored interview answer audio metadata."""
from __future__ import annotations

from typing import Any


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


def find_answer_audio(
    submission_data: dict | None,
    *,
    order: int | None = None,
    question_id: int | None = None,
) -> dict[str, Any] | None:
    """Find audio metadata for a question from stored answers/checkpoints."""
    for item in _iter_answer_records(submission_data):
        item_order = item.get("order")
        item_question_id = item.get("question_id")
        audio_key = item.get("audio_key")
        if not audio_key:
            continue

        if order is not None and item_order is not None and int(item_order) == int(order):
            return item
        if question_id is not None and item_question_id is not None and int(item_question_id) == int(question_id):
            return item

    if order is not None:
        for index, item in enumerate(_iter_answer_records(submission_data), start=1):
            if index == int(order) and item.get("audio_key"):
                return item
    return None


def list_answer_audio_items(submission_data: dict | None) -> list[dict[str, Any]]:
    """Return deduplicated answer records that include audio, ordered by question order."""
    seen_orders: set[int] = set()
    results: list[dict[str, Any]] = []

    for item in _iter_answer_records(submission_data):
        audio_key = item.get("audio_key")
        if not audio_key:
            continue
        order_val = item.get("order")
        order = int(order_val) if order_val is not None else len(results) + 1
        if order in seen_orders:
            continue
        seen_orders.add(order)
        results.append({**item, "order": order})

    results.sort(key=lambda row: row.get("order") or 0)
    return results
