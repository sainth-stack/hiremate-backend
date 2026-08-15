"""Difficulty mix for 15 generated questions."""
from __future__ import annotations

TOTAL_QUESTIONS = 15

DIFFICULTY_MIX: dict[str, dict[str, int]] = {
    "easy": {"easy": 10, "medium": 4, "hard": 1},
    "medium": {"easy": 4, "medium": 7, "hard": 4},
    "hard": {"easy": 2, "medium": 5, "hard": 8},
}

TEMPLATE_BY_COMPLEXITY = {
    "easy": "easy_view_card",
    "medium": "medium_view_card",
    "hard": "hard_view_card",
}

TIME_CARD_BY_COMPLEXITY = {
    "easy": {"duration": "2-3 min", "complexity": "Easy", "time_limit_seconds": 180},
    "medium": {"duration": "3-5 min", "complexity": "Medium", "time_limit_seconds": 300},
    "hard": {"duration": "5-7 min", "complexity": "Hard", "time_limit_seconds": 420},
}

TECHNICAL_COMPLEXITY_GUIDE = {
    "easy": (
        "Fundamentals: definitions, syntax, core concepts, basic usage, "
        "simple code explanation, tool/library basics."
    ),
    "medium": (
        "Applied technical: implementation details, debugging, APIs, patterns, "
        "state management, performance basics, practical coding scenarios."
    ),
    "hard": (
        "Advanced technical: system design, scalability, optimization, security, "
        "trade-offs, architecture decisions, edge cases, production problems."
    ),
}

NON_TECHNICAL_CATEGORY_MARKERS = {
    "behavioral",
    "hr",
    "culture",
    "soft skill",
    "leadership",
    "teamwork",
    "communication",
}

BEHAVIORAL_QUESTION_PATTERNS = (
    "describe a time",
    "tell me about a time",
    "give an example when",
    "situation where you",
    "how do you handle conflict",
    "how do you prioritize",
    "work with a team",
    "biggest weakness",
    "why do you want to join",
    "why should we hire",
    "where do you see yourself",
    "tell me about yourself",
    "received feedback",
)


def normalize_difficulty(value: str) -> str:
    v = (value or "medium").strip().lower()
    if v not in DIFFICULTY_MIX:
        return "medium"
    return v


def get_difficulty_mix(interview_difficulty: str) -> dict[str, int]:
    return DIFFICULTY_MIX[normalize_difficulty(interview_difficulty)].copy()
