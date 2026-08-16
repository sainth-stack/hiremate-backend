"""Persist and serialize generated interview questions."""
from sqlalchemy.orm import Session

from backend.app.models.interview import Interview
from backend.app.models.interview_question import InterviewQuestion
from backend.app.services.interview_question_generator.question_count import resolve_question_count
from backend.app.services.interview_summary import resolve_interview_summary
from backend.app.schemas.interview import InterviewDetailResponse, InterviewQuestionCardResponse


def save_interview_questions(
    db: Session,
    interview_id: int,
    generated: list[dict],
) -> list[InterviewQuestion]:
    objects: list[InterviewQuestion] = []
    for item in generated:
        obj = InterviewQuestion(
            interview_id=interview_id,
            order_index=item["order"],
            template=item["template"],
            category=item["category"],
            question_text=item["question_text"],
            overview=item.get("overview"),
            intent=item.get("intent"),
            expectations=item.get("expectations") or [],
            sample_answer=item.get("sample_answer"),
            star_breakdown=item.get("star_breakdown"),
            complexity=item["complexity"],
            duration=item["duration"],
            view_card=item["view_card"],
            time_card=item["time_card"],
        )
        db.add(obj)
        objects.append(obj)
    db.flush()
    return objects


def load_interview_questions(db: Session, interview_id: int) -> list[InterviewQuestion]:
    return (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.interview_id == interview_id)
        .order_by(InterviewQuestion.order_index)
        .all()
    )


def build_interview_detail(interview: Interview, questions: list[InterviewQuestion]) -> InterviewDetailResponse:
    return InterviewDetailResponse(
        id=interview.id,
        title=interview.title,
        difficulty=interview.difficulty,
        description=interview.description,
        summary=resolve_interview_summary(
            title=interview.title,
            description=interview.description,
            difficulty=interview.difficulty,
            summary=interview.summary,
        ),
        question_count=resolve_question_count(interview.question_count, interview.description),
        tts_speaker=interview.tts_speaker,
        tts_language_code=interview.tts_language_code,
        created_at=interview.created_at,
        questions=[
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
        ],
    )
