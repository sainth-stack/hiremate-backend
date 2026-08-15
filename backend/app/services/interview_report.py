"""Build interview report responses from stored evaluation payloads."""
from backend.app.schemas.interview import (
    InterviewQuestionReviewResponse,
    InterviewQuestionSummaryResponse,
    InterviewReportResponse,
)


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


def parse_question_review(item: dict, order: int) -> InterviewQuestionReviewResponse:
    return InterviewQuestionReviewResponse(
        order=int(item.get("order") or order),
        question=item.get("question") or "",
        user_answer=item.get("user_answer") or "",
        what_you_said=item.get("what_you_said") or item.get("user_answer") or "",
        how_to_answer=item.get("how_to_answer") or item.get("coaching_tip") or "",
        feedback=item.get("feedback"),
        score=item.get("score"),
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

    return InterviewReportResponse(
        score=int(report.get("score", 0)),
        summary=report.get("summary") or "",
        evaluation_summary=evaluation_summary,
        strengths=report.get("strengths") or [],
        improvements=report.get("improvements") or [],
        overall_score=report.get("overall_score"),
        final_score=report.get("final_score"),
        feedback=report.get("feedback"),
        evaluation=report.get("evaluation") or evaluation_summary,
        areas_for_improvement=report.get("areas_for_improvement"),
        weaknesses=report.get("weaknesses"),
        average_question_score=report.get("average_question_score") or _average_score(question_reviews),
        question_summaries=_question_summaries_from_reviews(question_reviews),
    )
