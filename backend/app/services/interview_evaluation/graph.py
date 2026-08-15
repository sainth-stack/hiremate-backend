"""LangGraph pipeline: evaluate all interview answers in one pass."""
from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, ValidationError

from backend.jobradar.services.llm_factory import LLMFactory
from backend.app.services.interview_evaluation.state import InterviewEvaluationState

logger = logging.getLogger(__name__)


class QuestionReviewItem(BaseModel):
    question: str
    user_answer: str = ""
    what_you_said: str = ""
    how_to_answer: str = ""
    feedback: str = ""
    score: int = Field(default=0, ge=0, le=100)


class BatchInterviewEvaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    summary: str
    evaluation_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    question_reviews: list[QuestionReviewItem] = Field(default_factory=list)


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM evaluation response must be a JSON object")
    return data


def _merge_question_reviews(
    submitted_answers: list[dict[str, str]],
    llm_reviews: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    llm_by_question = {}
    for item in llm_reviews or []:
        if isinstance(item, dict):
            key = (item.get("question") or "").strip().lower()
            if key:
                llm_by_question[key] = item

    merged: list[dict[str, Any]] = []
    for submitted in submitted_answers:
        question = (submitted.get("question") or "").strip()
        user_answer = (submitted.get("answer") or "").strip()
        llm_item = llm_by_question.get(question.lower(), {})

        what_you_said = (
            llm_item.get("what_you_said")
            or llm_item.get("user_answer")
            or user_answer
            or "No answer provided."
        )
        how_to_answer = (
            llm_item.get("how_to_answer")
            or llm_item.get("coaching_tip")
            or llm_item.get("improvement_tip")
            or "Structure your answer with context, your action, and measurable results."
        )

        merged.append(
            {
                "order": len(merged) + 1,
                "question": question,
                "user_answer": user_answer,
                "what_you_said": what_you_said,
                "how_to_answer": how_to_answer,
                "feedback": llm_item.get("feedback") or "",
                "score": int(llm_item.get("score", 0)) if llm_item.get("score") is not None else None,
            }
        )
    return merged


def prepare_evaluation_node(state: InterviewEvaluationState) -> InterviewEvaluationState:
    answers = state.get("answers") or []
    if not answers:
        return {**state, "error": "At least one answer is required"}
    return {**state, "error": None}


def evaluate_answers_node(state: InterviewEvaluationState) -> InterviewEvaluationState:
    if state.get("error"):
        return state

    qa_lines = []
    for index, item in enumerate(state.get("answers") or [], start=1):
        question = (item.get("question") or "").strip()
        answer = (item.get("answer") or "").strip()
        qa_lines.append(f"{index}. Question: {question}\n   Answer: {answer or '(no answer)'}")

    system_prompt = """
You are an expert interview coach evaluating a completed mock interview.

Return ONLY a JSON object with these keys:
- score: integer 0-100 overall performance score
- summary: 2-3 sentence brief overall assessment
- evaluation_summary: 4-5 sentence detailed overall assessment (two more lines of depth than summary — cover communication, technical accuracy, structure, and interview readiness)
- strengths: array of 3-5 concise strength bullets
- improvements: array of 3-5 actionable improvement bullets
- question_reviews: array with ONE object per question, in the same order as provided, each containing:
  - question: exact question text
  - user_answer: echo the candidate's answer
  - what_you_said: 1-2 sentence summary of what the candidate communicated
  - how_to_answer: concrete coaching on how to answer better (structure, STAR, metrics, clarity)
  - feedback: brief strengths/weaknesses for this answer
  - score: integer 0-100 for this specific answer

Evaluate holistically across all answers (communication, relevance, depth, STAR structure, technical accuracy).
Pure JSON only. No markdown fences.
"""
    user_prompt = (
        f"Interview title: {state.get('title', '')}\n"
        f"Difficulty: {state.get('difficulty', '')}\n"
        f"Job description:\n{state.get('jd', '')}\n\n"
        f"Candidate answers:\n" + "\n\n".join(qa_lines)
    )

    try:
        llm = LLMFactory.get_provider()
        raw = llm.generate(
            system_prompt,
            user_prompt,
            user_id=state.get("user_id"),
            email=state.get("email"),
            feature="admin_interview_evaluation",
        )
        parsed = _parse_json_object(raw)
        evaluation = BatchInterviewEvaluation(**parsed)
        return {
            **state,
            "raw_evaluation": evaluation.model_dump(),
            "error": None,
        }
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        logger.exception("Interview evaluation parsing failed")
        return {**state, "error": f"Evaluation parsing failed: {exc}"}
    except Exception as exc:
        logger.exception("Interview evaluation failed")
        return {**state, "error": str(exc)}


def format_report_node(state: InterviewEvaluationState) -> InterviewEvaluationState:
    if state.get("error"):
        return state

    raw = state.get("raw_evaluation") or {}
    question_reviews = _merge_question_reviews(
        state.get("answers") or [],
        raw.get("question_reviews"),
    )
    scores = [q["score"] for q in question_reviews if q.get("score") is not None]
    average_question_score = round(sum(scores) / len(scores)) if scores else None
    summary = raw.get("summary") or ""
    evaluation_summary = raw.get("evaluation_summary") or summary

    report = {
        "score": int(raw.get("score", 0)),
        "summary": summary,
        "evaluation_summary": evaluation_summary,
        "strengths": raw.get("strengths") or [],
        "improvements": raw.get("improvements") or [],
        "overall_score": int(raw.get("score", 0)),
        "final_score": int(raw.get("score", 0)),
        "feedback": evaluation_summary,
        "evaluation": evaluation_summary,
        "areas_for_improvement": raw.get("improvements") or [],
        "weaknesses": raw.get("improvements") or [],
        "average_question_score": average_question_score,
        "question_reviews": question_reviews,
    }
    return {**state, "report": report, "error": None}


def _route_on_error(state: InterviewEvaluationState) -> str:
    if state.get("error"):
        return "__end__"
    return "next"


def _build_graph():
    builder = StateGraph(InterviewEvaluationState)
    builder.add_node("prepare_evaluation", prepare_evaluation_node)
    builder.add_node("evaluate_answers", evaluate_answers_node)
    builder.add_node("format_report", format_report_node)

    builder.add_edge(START, "prepare_evaluation")
    builder.add_conditional_edges(
        "prepare_evaluation",
        _route_on_error,
        {"next": "evaluate_answers", "__end__": END},
    )
    builder.add_conditional_edges(
        "evaluate_answers",
        _route_on_error,
        {"next": "format_report", "__end__": END},
    )
    builder.add_edge("format_report", END)
    return builder.compile()


_GRAPH = None


def evaluate_interview_submission(
    *,
    user_id: int,
    email: str | None,
    interview_id: int,
    title: str,
    difficulty: str,
    jd: str,
    answers: list[dict[str, str]],
) -> dict[str, Any]:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()

    initial: InterviewEvaluationState = {
        "user_id": user_id,
        "email": email,
        "interview_id": interview_id,
        "title": title,
        "difficulty": difficulty,
        "jd": jd,
        "answers": answers,
        "raw_evaluation": {},
        "report": {},
        "error": None,
    }
    result = _GRAPH.invoke(initial)
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result.get("report") or {}
