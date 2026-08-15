"""LangGraph state for admin interview question generation."""
from typing import Any, TypedDict

MAX_GENERATION_RETRIES = 3


class InterviewQuestionGenerationState(TypedDict, total=False):
    title: str
    description: str
    difficulty: str
    user_id: int | None
    email: str | None
    total_questions: int
    difficulty_mix: dict[str, int]
    technical_skills: list[str]
    raw_questions: list[dict[str, Any]]
    validated_questions: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    retry_count: int
    error: str | None
