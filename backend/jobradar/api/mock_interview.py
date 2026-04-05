from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.user import User
from backend.jobradar.models.application import Application
from backend.jobradar.models.mock_interview import MockInterviewSession
from backend.jobradar.services.interview_service import InterviewService

router = APIRouter()

@router.get("/questions")
def get_interview_questions(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch tailored interview questions for a specific application.
    If no questions exist in cache, they will be generated via AI.
    """
    app = db.query(Application).filter(
        Application.id == application_id, 
        Application.user_id == current_user.id
    ).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    service = InterviewService(db)
    questions = service.get_or_generate_questions(app.company, app.role)
    
    return [
        {
            "id": q.id,
            "category": q.category,
            "question_text": q.question_text,
            "overview": q.overview,
            "intent": q.intent,
            "expectations": q.expectations,
            "sampleAnswer": q.sample_answer,
            "starBreakdown": q.star_breakdown,
            "complexity": q.complexity,
            "duration": q.duration
        }
        for q in questions
    ]

@router.post("/load-more")
def load_more_questions(
    application_id: int,
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Force-generate 5 additional unique questions for the given application.
    """
    app = db.query(Application).filter(
        Application.id == application_id, 
        Application.user_id == current_user.id
    ).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    service = InterviewService(db)
    
    # Get current count specifically for this category if provided
    from backend.jobradar.models.mock_interview import MockInterviewQuestion
    query = db.query(MockInterviewQuestion).filter(
        MockInterviewQuestion.company_name == app.company.strip().lower(),
        MockInterviewQuestion.role_title == app.role.strip().lower()
    )
    if category:
        query = query.filter(MockInterviewQuestion.category.ilike(f"%{category}%"))
    
    current_count = query.count()
    
    # Ask for 5 more, excluding the ones we already have
    existing_q_query = db.query(MockInterviewQuestion).filter(
        MockInterviewQuestion.company_name == app.company.strip().lower(),
        MockInterviewQuestion.role_title == app.role.strip().lower()
    )
    if category:
        existing_q_query = existing_q_query.filter(MockInterviewQuestion.category.ilike(f"%{category}%"))
        
    existing_texts = [q.question_text for q in existing_q_query.all()]
    
    questions = service.get_or_generate_questions(
        app.company, 
        app.role, 
        count=current_count + 5,
        exclude_list=existing_texts,
        category=category
    )
    
    return {"success": True, "new_count": len(questions)}


@router.post("/session/evaluate")
def evaluate_interview_answer(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Evaluates a single answer using AI and returns STAR feedback.
    """
    app_id = payload.get("application_id")
    question = payload.get("question")
    answer = payload.get("answer")
    
    app = db.query(Application).filter(Application.id == app_id, Application.user_id == current_user.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    service = InterviewService(db)
    evaluation = service.evaluate_answer(question, answer, app.company, app.role)
    
    if not evaluation:
        raise HTTPException(status_code=500, detail="AI evaluation failed")
        
    return evaluation


@router.post("/session/save")
def save_interview_session(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Saves a completed interview session to history.
    """
    app_id = payload.get("application_id")
    app = db.query(Application).filter(Application.id == app_id, Application.user_id == current_user.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    service = InterviewService(db)
    session = service.save_session_results(current_user.id, app.id, payload)
    
    return {"success": True, "session_id": session.id}


@router.get("/history")
def get_interview_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches the user's interview session history.
    """
    sessions = (
        db.query(MockInterviewSession)
        .filter(MockInterviewSession.user_id == current_user.id)
        .order_by(MockInterviewSession.created_at.desc())
        .all()
    )
    
    return [
        {
            "id": s.id,
            "application_id": s.application_id,
            "score": s.total_score,
            "duration": s.duration_seconds,
            "date": s.created_at.isoformat(),
            "answer_count": len(s.answers)
        }
        for s in sessions
    ]


@router.get("/session/{session_id}")
def get_interview_session_detail(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches the full details of a specific interview session, including answers.
    """
    session = db.query(MockInterviewSession).filter(
        MockInterviewSession.id == session_id,
        MockInterviewSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "id": session.id,
        "application_id": session.application_id,
        "score": session.total_score,
        "duration": session.duration_seconds,
        "date": session.created_at.isoformat(),
        "answers": [
            {
                "id": a.id,
                "question": a.question_text,
                "category": a.category,
                "answer": a.user_answer,
                "star_score": a.star_score,
                "star_breakdown": a.star_breakdown,
                "feedback": a.ai_feedback,
                "created_at": a.created_at.isoformat()
            }
            for a in session.answers
        ]
    }
