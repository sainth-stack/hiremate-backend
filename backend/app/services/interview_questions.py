"""Serialize and ensure interview questions for API responses."""
from sqlalchemy.orm import Session

from backend.app.models.interview import Interview
from backend.app.models.interview_question import InterviewQuestion
from backend.app.schemas.interview import InterviewQuestionCardResponse, LiveInterviewQuestionResponse
from backend.app.services.interview_question_generator import generate_interview_questions
from backend.app.services.interview_question_generator.persistence import (
    load_interview_questions,
    save_interview_questions,
)


def to_question_card_responses(questions: list[InterviewQuestion]) -> list[InterviewQuestionCardResponse]:
    return [
        InterviewQuestionCardResponse(
            id=q.id,
            order=q.order_index,
            template=q.template,
            view_card=q.view_card,
            time_card=q.time_card,
            category=q.category,
            question_text=q.question_text,
            overview=q.overview,
            intent=q.intent,
            expectations=q.expectations or [],
            sample_answer=q.sample_answer,
            star_breakdown=q.star_breakdown,
            complexity=q.complexity,
            duration=q.duration,
        )
        for q in sorted(questions, key=lambda x: x.order_index)
    ]


def to_live_question_responses(questions: list[InterviewQuestion]) -> list[LiveInterviewQuestionResponse]:
    return [
        LiveInterviewQuestionResponse(
            id=q.id,
            order=q.order_index,
            question_text=q.question_text,
            category=q.category,
            complexity=q.complexity,
            duration=q.duration,
            overview=q.overview,
        )
        for q in sorted(questions, key=lambda x: x.order_index)
    ]


def ensure_interview_questions(
    db: Session,
    interview: Interview,
    *,
    user_id: int | None = None,
    email: str | None = None,
) -> list[InterviewQuestion]:
    """Return stored questions, generating them for legacy templates that have none."""
    rows = load_interview_questions(db, interview.id)
    if rows:
        return rows

    generated = generate_interview_questions(
        title=interview.title,
        description=interview.description,
        difficulty=interview.difficulty,
        user_id=user_id,
        email=email,
        question_count=interview.question_count or 15,
    )
    rows = save_interview_questions(db, interview.id, generated)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows
