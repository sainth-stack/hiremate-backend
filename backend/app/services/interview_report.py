"""Build interview report responses from stored evaluation payloads."""
from backend.app.schemas.interview import (
    InterviewCategoryScoreResponse,
    InterviewHiringRecommendationResponse,
    InterviewQuestionReviewResponse,
    InterviewQuestionSummaryResponse,
    InterviewReportResponse,
)
from backend.app.services.interview_evaluation.scoring import score_status_label


def _question_summaries_from_reviews(raw_items: list | None) -> list[InterviewQuestionSummaryResponse]:
    summaries: list[InterviewQuestionSummaryResponse] = []
    for index, item in enumerate(raw_items or [], start=1):
        if not isinstance(item, dict):
            continue
        summaries.append(
            InterviewQuestionSummaryResponse(
                order=int(item.get("order") or index),
                question=item.get("question") or "",
                score=item.get("score"),
                category=item.get("category"),
                question_type=item.get("question_type"),
            )
        )
    return summaries


def _average_score(raw_items: list | None) -> int | None:
    scores = [
        int(item.get("score"))
        for item in (raw_items or [])
        if isinstance(item, dict) and item.get("score") is not None
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores))


def _normalize_dimensions(raw: dict | None) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    cleaned: dict[str, int] = {}
    for key, value in raw.items():
        if value is None:
            continue
        try:
            cleaned[str(key)] = max(0, min(100, int(value)))
        except (TypeError, ValueError):
            continue
    return cleaned or None


def parse_question_review(item: dict, order: int) -> InterviewQuestionReviewResponse:
    return InterviewQuestionReviewResponse(
        order=int(item.get("order") or order),
        question=item.get("question") or "",
        user_answer=item.get("user_answer") or "",
        what_you_said=item.get("what_you_said") or item.get("user_answer") or "",
        how_to_answer=(
            item.get("how_to_answer")
            or item.get("better_answer")
            or item.get("coaching_tip")
            or ""
        ),
        feedback=item.get("feedback"),
        score=item.get("score"),
        question_type=item.get("question_type"),
        category=item.get("category"),
        what_went_well=item.get("what_went_well") or item.get("what_you_said"),
        what_was_missing=item.get("what_was_missing"),
        better_answer=item.get("better_answer") or item.get("how_to_answer"),
        recommended_improvement=(
            item.get("recommended_improvement")
            or item.get("feedback")
        ),
        dimensions=_normalize_dimensions(item.get("dimensions")),
    )


def get_stored_question_review(report: dict | None, order: int) -> InterviewQuestionReviewResponse | None:
    if not report or not isinstance(report, dict):
        return None
    reviews = report.get("question_reviews") or []
    for index, item in enumerate(reviews, start=1):
        if not isinstance(item, dict):
            continue
        item_order = int(item.get("order") or index)
        if item_order == order:
            return parse_question_review(item, item_order)
    return None


def build_report_response(report: dict | None) -> InterviewReportResponse | None:
    """Public report shape — summaries only, no full per-question answers."""
    if not report or not isinstance(report, dict):
        return None

    question_reviews = report.get("question_reviews") or []
    evaluation_summary = (
        report.get("evaluation_summary")
        or report.get("summary")
        or ""
    )
    overall_score = int(report.get("score") or report.get("overall_score") or 0)
    categories = [
        InterviewCategoryScoreResponse(name=item["name"], score=int(item["score"]))
        for item in (report.get("categories") or [])
        if isinstance(item, dict) and item.get("name") is not None and item.get("score") is not None
    ]
    hiring_raw = report.get("hiring_recommendation")
    hiring = None
    if isinstance(hiring_raw, dict) and hiring_raw.get("recommendation"):
        hiring = InterviewHiringRecommendationResponse(
            recommendation=str(hiring_raw.get("recommendation")),
            confidence=int(hiring_raw.get("confidence") or 0),
            reason=str(hiring_raw.get("reason") or ""),
        )

    return InterviewReportResponse(
        score=overall_score,
        summary=report.get("summary") or "",
        evaluation_summary=evaluation_summary,
        strengths=report.get("strengths") or [],
        improvements=report.get("improvements") or [],
        recommendations=report.get("recommendations") or [],
        categories=categories,
        score_status=report.get("score_status") or score_status_label(overall_score),
        score_calculation_note=report.get("score_calculation_note"),
        overall_score=report.get("overall_score") or overall_score,
        final_score=report.get("final_score") or overall_score,
        feedback=report.get("feedback"),
        evaluation=report.get("evaluation") or evaluation_summary,
        areas_for_improvement=report.get("areas_for_improvement"),
        weaknesses=report.get("weaknesses"),
        average_question_score=report.get("average_question_score") or _average_score(question_reviews),
        hiring_recommendation=hiring,
        interview_title=report.get("interview_title"),
        interview_type=report.get("interview_type"),
        question_summaries=_question_summaries_from_reviews(question_reviews),
    )
