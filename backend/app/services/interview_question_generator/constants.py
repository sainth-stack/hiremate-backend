"""Default difficulty mix ratios (scaled to total question count)."""
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


def get_difficulty_mix(interview_difficulty: str, total_questions: int = TOTAL_QUESTIONS) -> dict[str, int]:
    base = DIFFICULTY_MIX[normalize_difficulty(interview_difficulty)].copy()
    return scale_difficulty_mix(base, total_questions)


def scale_difficulty_mix(base: dict[str, int], total: int) -> dict[str, int]:
    """Scale easy/medium/hard counts to match total question count."""
    total = max(3, min(int(total), 30))
    base_total = sum(base.values()) or 1
    keys = ["easy", "medium", "hard"]
    result: dict[str, int] = {}
    allocated = 0
    for index, key in enumerate(keys):
        if index == len(keys) - 1:
            result[key] = max(0, total - allocated)
        else:
            count = int(round(base.get(key, 0) * total / base_total))
            result[key] = count
            allocated += count
    if sum(result.values()) == 0:
        result["medium"] = total
    elif sum(result.values()) != total:
        result["medium"] = max(0, result.get("medium", 0) + (total - sum(result.values())))
    return result
