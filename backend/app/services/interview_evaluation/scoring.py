"""Deterministic interview score helpers."""
from __future__ import annotations

from typing import Any


def score_status_label(score: int) -> str:
    value = max(0, min(100, int(score or 0)))
    if value >= 90:
        return "Excellent"
    if value >= 75:
        return "Strong"
    if value >= 60:
        return "Good"
    if value >= 40:
        return "Needs Improvement"
    return "Requires Significant Improvement"


def average_question_score(question_reviews: list[dict[str, Any]]) -> int | None:
    scores = [
        int(item["score"])
        for item in question_reviews
        if isinstance(item, dict) and item.get("score") is not None
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores))


def compute_overall_score(question_reviews: list[dict[str, Any]], llm_score: int | None = None) -> int:
    """Use the mean of per-question scores as the authoritative overall score."""
    avg = average_question_score(question_reviews)
    if avg is not None:
        return avg
    if llm_score is not None:
        return max(0, min(100, int(llm_score)))
    return 0


def compute_category_scores(
    question_reviews: list[dict[str, Any]],
    llm_categories: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Aggregate per-question scores by category; fall back to LLM categories if needed."""
    buckets: dict[str, list[int]] = {}
    for item in question_reviews:
        if not isinstance(item, dict):
            continue
        category = (item.get("category") or "").strip()
        score = item.get("score")
        if not category or score is None:
            continue
        buckets.setdefault(category, []).append(int(score))

    if buckets:
        return [
            {"name": name, "score": round(sum(values) / len(values))}
            for name, values in sorted(buckets.items(), key=lambda pair: pair[0].lower())
        ]

    normalized: list[dict[str, Any]] = []
    for item in llm_categories or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or item.get("category") or "").strip()
        score = item.get("score")
        if name and score is not None:
            normalized.append({"name": name, "score": max(0, min(100, int(score)))})
    return normalized


def build_hiring_recommendation(overall_score: int, evaluation_summary: str) -> dict[str, Any]:
    score = max(0, min(100, int(overall_score or 0)))
    if score >= 80:
        recommendation = "Proceed to Next Round"
        confidence = min(95, 70 + score // 5)
    elif score >= 65:
        recommendation = "Proceed with Follow-up"
        confidence = min(88, 55 + score // 4)
    elif score >= 50:
        recommendation = "Borderline — Additional Review Recommended"
        confidence = min(75, 40 + score // 3)
    else:
        recommendation = "Does Not Meet Bar"
        confidence = min(85, 50 + (100 - score) // 4)

    reason = (evaluation_summary or "").strip()
    if len(reason) > 280:
        reason = reason[:277].rstrip() + "..."

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "reason": reason or "AI recommendation based on interview performance evidence.",
    }
