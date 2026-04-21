import json
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.jobradar.models.mock_interview import MockInterviewQuestion, MockInterviewSession, MockInterviewAnswer
from backend.jobradar.services.llm_factory import LLMFactory
from backend.jobradar.services.classifier import InterviewQuestionData, InterviewEvaluationOutput

logger = logging.getLogger(__name__)

class InterviewService:
    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMFactory.get_provider()

    def get_or_generate_questions(
        self, 
        company: str, 
        role: str, 
        user_id: int,
        email: str,
        count: int = 5,
        exclude_list: List[str] = None,
        category: str = None
    ) -> List[MockInterviewQuestion]:
        """
        Main entry point: fetches from cache or generates with AI.
        """
        company_norm = company.strip().lower()
        role_norm = role.strip().lower()

        # 1. Check Cache (Scope to category if provided)
        query = self.db.query(MockInterviewQuestion).filter(
            MockInterviewQuestion.company_name == company_norm,
            MockInterviewQuestion.role_title == role_norm,
            MockInterviewQuestion.is_global == True
        )
        if category:
            query = query.filter(MockInterviewQuestion.category.ilike(f"%{category}%"))
            
        existing = query.all()

        if len(existing) >= count:
            logger.info(f"CACHE HIT: Found {len(existing)} questions for {company}/{role}")
            return existing

        # 2. Generate More
        needed = count - len(existing)
        logger.info(f"CACHE MISS: Generating {needed} more questions for {company}/{role}")
        
        # If we already have some questions, send them as excluded to ensure uniqueness
        if not exclude_list and existing:
            exclude_list = [q.question_text for q in existing]
            
        new_questions_data = self._generate_ai_questions(company, role, needed, user_id, email, exclude_list, category)
        
        new_objects = []
        for q_data_raw in new_questions_data:
            # Senior style: Robust type checking and Pydantic validation
            if not isinstance(q_data_raw, dict):
                logger.warning(f"AI: Skipping non-object item: {q_data_raw}")
                continue
                
            try:
                # Validation & Defaults via Pydantic
                q_data = InterviewQuestionData(**q_data_raw)
                
                q_obj = MockInterviewQuestion(
                    company_name=company_norm,
                    role_title=role_norm,
                    category=q_data.category,
                    question_text=q_data.question_text,
                    overview=q_data.overview,
                    intent=q_data.intent,
                    expectations=q_data.expectations,
                    sample_answer=q_data.sample_answer,
                    star_breakdown=q_data.star_breakdown,
                    complexity=q_data.complexity,
                    duration=q_data.duration,
                    is_global=True
                )
                self.db.add(q_obj)
                new_objects.append(q_obj)
            except Exception as val_err:
                logger.error(f"AI Validation failed for item: {val_err}")
                continue

        self.db.commit()
        for obj in new_objects:
            self.db.refresh(obj)

        return existing + new_objects

    def _generate_ai_questions(self, company: str, role: str, count: int, user_id: int, email: str, exclude_list: List[str] = None, category: str = None) -> List[Dict]:
        """
        Calls the LLM to generate structured question data using system/user separation.
        """
        system_prompt = f"""
        You are a world-class hiring manager and interviewer. 
        Your task is to generate {count} tailored interview questions in a structured format.
        
        Return ONLY a JSON list of objects with these exact keys:
        - category: ('Behavioral', 'Technical', or 'HR & Culture')
        - question_text: (The actual question prompt)
        - overview: (A 1-sentence context)
        - intent: (The hidden objective of this question)
        - expectations: (List of 3 success criteria)
        - sample_answer: (High-impact model answer)
        - star_breakdown: (Dict with s, t, a, r as booleans)
        - complexity: ('Easy', 'Medium', or 'Hard')
        - duration: ('2-3 min')

        Ensure the output is pure JSON. No markdown, no triple backticks.
        """

        if exclude_list:
            system_prompt += f"\nCRITICAL: Do not repeat these existing questions:\n - " + "\n - ".join(exclude_list)
            
        if category:
            system_prompt += f"\nFATAL: Every single question in the response MUST belong to the category: '{category}'."

        user_prompt = f"Generate {count} questions for a {role} position at {company}."
        
        try:
            # We call generate(system, user)
            response_text = self.llm.generate(
                system_prompt, 
                user_prompt, 
                user_id=user_id, 
                email=email,
                feature="interview_questions"
            )
            
            # Use consistent parsing logic as seen in other modules
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(response_text)
            
            # Robust extraction: if the AI wraps the list in an object (common error)
            if isinstance(data, dict):
                # Search for any top-level key that holds a list
                for val in data.values():
                    if isinstance(val, list):
                        return val
                return [] # No list found in object
                
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"AI Generation failed: {str(e)}")
            return []

    def evaluate_answer(self, question: str, answer: str, company: str, role: str, user_id: int, email: str) -> Optional[InterviewEvaluationOutput]:
        """
        Evaluates a single interview answer using the LLM against STAR principles.
        """
        system_prompt = f"""
        You are an elite Executive Coach and Interviewer. 
        Evaluate the following candidate's answer for a {role} position at {company}.
        
        Question: {question}
        User Answer: {answer}

        Your task is to provide a structured evaluation based on STAR (Situation, Task, Action, Result) principles.
        
        Return ONLY a JSON object with these exact keys:
        - star_score: (Integer 0-100 representing overall quality)
        - star_breakdown: (Dict with s, t, a, r as booleans indicating if each part was clearly mentioned)
        - feedback: (Expert assessment of the answer's strengths and weaknesses - max 2 sentences)
        - ai_coaching_tip: (One specific, actionable tip for improvement)

        Ensure the output is pure JSON. No markdown, no triple backticks.
        """

        try:
            response_text = self.llm.generate(
                system_prompt, 
                "", 
                user_id=user_id, 
                email=email,
                feature="interview_evaluation"
            )
            
            # Robust parsing (handles markdown wrapper)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(response_text)
            return InterviewEvaluationOutput(**data)
        except Exception as e:
            logger.error(f"AI Evaluation failed: {str(e)}")
            return None

    def save_session_results(self, user_id: int, application_id: int, session_data: dict) -> MockInterviewSession:
        """
        Saves the complete interview session and its constituent answers.
        """
        session = MockInterviewSession(
            user_id=user_id,
            application_id=application_id,
            total_score=session_data.get("total_score", 0),
            duration_seconds=session_data.get("duration_seconds", 0)
        )
        self.db.add(session)
        self.db.flush()

        for ans_data in session_data.get("answers", []):
            feedback_raw = ans_data.get("feedback")
            if isinstance(feedback_raw, dict):
                feedback_str = feedback_raw.get("feedback", json.dumps(feedback_raw))
            else:
                feedback_str = str(feedback_raw) if feedback_raw else ""

            answer_obj = MockInterviewAnswer(
                session_id=session.id,
                question_text=ans_data.get("question"),
                category=ans_data.get("category"),
                user_answer=ans_data.get("answer"),
                star_score=ans_data.get("star_score", 0),
                star_breakdown=ans_data.get("star_breakdown"),
                ai_feedback=feedback_str
            )
            self.db.add(answer_obj)

        self.db.commit()
        self.db.refresh(session)
        return session
