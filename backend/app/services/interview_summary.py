"""Generate short candidate-facing interview summaries."""
from __future__ import annotations

import logging
import re

from backend.jobradar.services.llm_factory import LLMFactory

logger = logging.getLogger(__name__)

MAX_SUMMARY_LEN = 320


def _strip_markdown(text: str) -> str:
    cleaned = re.sub(r"#{1,6}\s*", "", text or "")
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\n+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _clamp_summary(text: str) -> str:
    cleaned = _strip_markdown(text).strip()
    if len(cleaned) <= MAX_SUMMARY_LEN:
        return cleaned
    trimmed = cleaned[: MAX_SUMMARY_LEN - 1].rsplit(" ", 1)[0]
    return f"{trimmed}…"


def _looks_like_internal_prompt(text: str) -> bool:
    lowered = (text or "").lower()
    markers = [
        "ask exactly",
        "section 1",
        "listen for",
        "do not generate",
        "question_count",
        "one question at a time",
        "**q",
    ]
    return sum(1 for marker in markers if marker in lowered) >= 2


def fallback_interview_summary(*, title: str, description: str, difficulty: str) -> str:
    plain = _strip_markdown(description)
    if _looks_like_internal_prompt(plain):
        return _clamp_summary(
            f"A {difficulty.strip().lower()} {title.strip()} focused on relevant skills, "
            "project experience, and practical problem-solving."
        )
    sentences = re.split(r"(?<=[.!?])\s+", plain)
    parts: list[str] = []
    length = 0
    for sentence in sentences:
        chunk = sentence.strip()
        if not chunk:
            continue
        if length + len(chunk) > MAX_SUMMARY_LEN and parts:
            break
        parts.append(chunk)
        length += len(chunk) + 1
        if len(parts) >= 3:
            break

    if not parts:
        parts = [f"A {difficulty.strip().lower()} interview focused on {title.strip()}."]

    return _clamp_summary(" ".join(parts))


def generate_interview_summary(
    *,
    title: str,
    description: str,
    difficulty: str,
    user_id: int | None = None,
    email: str | None = None,
) -> str:
    """Create a 2–3 sentence plain-English summary for emails and candidate UI."""
    fallback = fallback_interview_summary(title=title, description=description, difficulty=difficulty)
    try:
        llm = LLMFactory.get_provider()
        system_prompt = (
            "You write short candidate-facing interview summaries. "
            "Return plain text only — no markdown, bullets, headings, or labels."
        )
        user_prompt = f"""Write exactly 2 short sentences (max 280 characters total) describing what this interview assesses.

Rules:
- Plain English for a job candidate
- Do NOT copy interview instructions, question lists, or internal prompts
- Do NOT mention question counts or section names
- Focus on role, skills, and difficulty at a high level

Title: {title.strip()}
Difficulty: {difficulty.strip()}
Admin context (internal only — summarize, do not repeat):
{description.strip()[:5000]}
"""
        raw = llm.generate(
            system_prompt,
            user_prompt,
            user_id=user_id,
            email=email,
            feature="admin_interview_summary",
        )
        summary = _clamp_summary(raw or "")
        return summary or fallback
    except Exception as exc:
        logger.warning("Interview summary LLM failed, using fallback: %s", exc)
        return fallback


def resolve_interview_summary(
    *,
    title: str,
    description: str,
    difficulty: str,
    summary: str | None = None,
) -> str:
    cleaned = (summary or "").strip()
    if cleaned:
        return _clamp_summary(cleaned)
    return fallback_interview_summary(title=title, description=description, difficulty=difficulty)
