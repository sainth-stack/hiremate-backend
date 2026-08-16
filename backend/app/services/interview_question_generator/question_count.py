"""Resolve how many questions to generate for an interview."""
from __future__ import annotations

import re

from backend.app.services.interview_question_generator.constants import TOTAL_QUESTIONS

_QUESTION_COUNT_PATTERNS = (
    re.compile(r"(?:ask|generate|prepare|create)\s+(?:exactly\s+)?(\d+)\s+questions?", re.IGNORECASE),
    re.compile(r"(\d+)\s+questions?\s+exactly", re.IGNORECASE),
    re.compile(r"exactly\s+(\d+)\s+questions?", re.IGNORECASE),
    re.compile(r"(\d+)\s+questions?\s+(?:total|in total)", re.IGNORECASE),
)
_SECTION_COUNT_PATTERN = re.compile(r"ask\s+(\d+)\s+questions?\.?", re.IGNORECASE)


def _normalize_description_for_parsing(description: str) -> str:
    """Strip markdown emphasis so counts like **20 questions** still parse."""
    text = description or ""
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"_+", "", text)
    return text


def infer_question_count_from_description(description: str | None) -> int | None:
    """Best-effort parse of explicit total question counts in interview context text."""
    if not description:
        return None

    normalized = _normalize_description_for_parsing(description)
    for pattern in _QUESTION_COUNT_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        count = int(match.group(1))
        if 3 <= count <= 30:
            return count
    return None


def infer_section_question_total(description: str | None) -> int | None:
    """
    Sum per-section counts like 'Ask 4 questions.' under topic headings.
    Skips the overall total line (e.g. 'Ask 20 questions exactly').
    """
    if not description:
        return None

    normalized = _normalize_description_for_parsing(description)
    section_counts: list[int] = []
    for match in _SECTION_COUNT_PATTERN.finditer(normalized):
        line_start = normalized.rfind("\n", 0, match.start()) + 1
        line_end = normalized.find("\n", match.end())
        if line_end == -1:
            line_end = len(normalized)
        line = normalized[line_start:line_end].lower()
        if "exactly" in line:
            continue
        count = int(match.group(1))
        if 1 <= count <= 10:
            section_counts.append(count)

    if len(section_counts) < 2:
        return None

    total = sum(section_counts)
    if 3 <= total <= 30:
        return total
    return None


def resolve_question_count(
    question_count: int | None,
    description: str | None = None,
    *,
    requested_count: int | None = None,
) -> int:
    """
    Resolve target question count.

    Priority:
    1. Explicit count from request payload (UI / API body)
    2. Explicit non-default stored count (user picked a value other than 15)
    3. Description hints (overall total or summed section counts)
    4. Stored default (15)
    5. Fallback default (15)
    """
    if requested_count is not None:
        value = int(requested_count)
        if value >= 3:
            return max(3, min(value, 30))

    inferred = infer_question_count_from_description(description)
    section_total = infer_section_question_total(description)

    stored: int | None = None
    if question_count is not None:
        value = int(question_count)
        if value >= 3:
            stored = max(3, min(value, 30))

    # User explicitly chose a non-default count in the UI.
    if stored is not None and stored != TOTAL_QUESTIONS:
        return stored

    candidates: list[int] = []
    if inferred is not None:
        candidates.append(inferred)
    if section_total is not None:
        candidates.append(section_total)
    if stored is not None:
        candidates.append(stored)

    if candidates:
        return max(candidates)

    return TOTAL_QUESTIONS
