"""LangGraph state for batch interview answer evaluation."""
from typing import Any, TypedDict


class InterviewEvaluationState(TypedDict, total=False):
    user_id: int
    email: str | None
    interview_id: int
    title: str
    difficulty: str
    jd: str
    answers: list[dict[str, str]]
    raw_evaluation: dict[str, Any]
    report: dict[str, Any]
    error: str | None
