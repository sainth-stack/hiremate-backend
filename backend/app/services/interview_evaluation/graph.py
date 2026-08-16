"""LangGraph pipeline: evaluate all interview answers in one pass."""
from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, ValidationError

from backend.jobradar.services.llm_factory import LLMFactory
from backend.app.services.interview_evaluation.scoring import (
    average_question_score,
    build_hiring_recommendation,
    compute_category_scores,
    compute_overall_score,
    score_status_label,
)
from backend.app.services.interview_evaluation.state import InterviewEvaluationState

logger = logging.getLogger(__name__)


class QuestionDimensions(BaseModel):
    technical_correctness: int | None = Field(default=None, ge=0, le=100)
    completeness: int | None = Field(default=None, ge=0, le=100)
    depth: int | None = Field(default=None, ge=0, le=100)
    practical_understanding: int | None = Field(default=None, ge=0, le=100)
    problem_solving: int | None = Field(default=None, ge=0, le=100)
    communication: int | None = Field(default=None, ge=0, le=100)
    structure: int | None = Field(default=None, ge=0, le=100)
    relevance: int | None = Field(default=None, ge=0, le=100)


class QuestionReviewItem(BaseModel):
    question: str
    user_answer: str = ""
    question_type: str = "technical"
    category: str = "General"
    what_you_said: str = ""
    what_went_well: str = ""
    what_was_missing: str = ""
    how_to_answer: str = ""
    better_answer: str = ""
    recommended_improvement: str = ""
    feedback: str = ""
    score: int = Field(default=0, ge=0, le=100)
    dimensions: QuestionDimensions | None = None


class CategoryScoreItem(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)


class BatchInterviewEvaluation(BaseModel):
    summary: str
    evaluation_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    categories: list[CategoryScoreItem] = Field(default_factory=list)
    question_reviews: list[QuestionReviewItem] = Field(default_factory=list)
    score: int | None = Field(default=None, ge=0, le=100)


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


def _infer_question_type(question: str, category: str | None, template: str | None = None) -> str:
    text = f"{question} {category or ''} {template or ''}".lower()
    behavioral_markers = (
        "tell me about a time", "describe a situation", "conflict", "leadership",
        "teamwork", "behavioral", "star", "challenge you faced", "worked with a difficult",
    )
    coding_markers = (
        "write code", "implement", "function", "algorithm", "complexity", "leetcode",
        "data structure", "pseudocode", "code snippet",
    )
    genai_markers = (
        "llm", "rag", "embedding", "vector", "langchain", "langgraph", "agent",
        "prompt", "fine-tun", "retrieval", "transformer", "gen ai", "genai",
    )
    if any(marker in text for marker in behavioral_markers):
        return "behavioral"
    if any(marker in text for marker in coding_markers):
        return "coding"
    if any(marker in text for marker in genai_markers):
        return "genai"
    return "technical"


def _coaching_framework(question_type: str) -> str:
    if question_type == "behavioral":
        return "Use STAR (Situation, Task, Action, Result) with measurable outcomes."
    if question_type == "coding":
        return "Use Problem Understanding → Approach → Implementation → Complexity → Edge Cases."
    if question_type == "genai":
        return "Use Concept → Architecture → Implementation → Trade-offs → Production Considerations."
    return "Use Concept → Approach → Example → Reasoning → Complexity / Trade-offs."


def _merge_question_reviews(
    submitted_answers: list[dict[str, Any]],
    llm_reviews: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    llm_by_question: dict[str, dict[str, Any]] = {}
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
        question_type = (
            llm_item.get("question_type")
            or _infer_question_type(
                question,
                submitted.get("category") or llm_item.get("category"),
                submitted.get("template"),
            )
        )
        category = (
            llm_item.get("category")
            or submitted.get("category")
            or question_type.replace("_", " ").title()
        )
        what_went_well = (
            llm_item.get("what_went_well")
            or llm_item.get("what_you_said")
            or ""
        )
        what_was_missing = llm_item.get("what_was_missing") or ""
        better_answer = (
            llm_item.get("better_answer")
            or llm_item.get("how_to_answer")
            or llm_item.get("coaching_tip")
            or ""
        )
        recommended_improvement = (
            llm_item.get("recommended_improvement")
            or llm_item.get("improvement_tip")
            or llm_item.get("feedback")
            or ""
        )
        how_to_answer = better_answer or recommended_improvement
        what_you_said = llm_item.get("what_you_said") or what_went_well or user_answer or "No answer provided."

        dimensions_raw = llm_item.get("dimensions")
        dimensions = dimensions_raw if isinstance(dimensions_raw, dict) else None

        merged.append(
            {
                "order": len(merged) + 1,
                "question": question,
                "user_answer": user_answer,
                "question_type": question_type,
                "category": category,
                "what_you_said": what_you_said,
                "what_went_well": what_went_well,
                "what_was_missing": what_was_missing,
                "how_to_answer": how_to_answer,
                "better_answer": better_answer,
                "recommended_improvement": recommended_improvement,
                "feedback": llm_item.get("feedback") or "",
                "score": int(llm_item.get("score", 0)) if llm_item.get("score") is not None else None,
                "dimensions": dimensions,
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
        category = (item.get("category") or "General").strip()
        complexity = (item.get("complexity") or "medium").strip()
        expectations = item.get("expectations")
        expectation_text = ""
        if isinstance(expectations, list):
            expectation_text = "; ".join(str(x) for x in expectations if x)
        elif isinstance(expectations, str):
            expectation_text = expectations

        qa_lines.append(
            f"{index}. Question: {question}\n"
            f"   Category hint: {category}\n"
            f"   Difficulty: {complexity}\n"
            f"   Expected concepts: {expectation_text or 'Not specified'}\n"
            f"   Answer: {answer or '(no answer)'}"
        )

    system_prompt = """
You are an expert technical interviewer evaluating a completed AI interview.

Return ONLY a JSON object with these keys:
- summary: 2-3 sentence brief overall assessment grounded in evidence from the answers
- evaluation_summary: 4-6 sentence detailed assessment referencing specific strengths and gaps observed
- strengths: array of 3-5 specific strengths tied to actual answer evidence (no generic filler)
- improvements: array of 3-5 actionable improvement areas (specific, not "practice more")
- recommendations: array of 3-5 study/practice topics based on weak areas from this interview
- categories: array of relevant competency/category scores actually assessed in this interview.
  Each item: { "name": "<category label>", "score": 0-100 }
  Use dynamic labels based on interview content (e.g. Python Fundamentals, RAG, LangGraph, Communication).
  Only include categories evidenced by the questions asked. Do not invent unused categories.
- question_reviews: array with ONE object per question, same order as provided. Each object:
  - question: exact question text
  - user_answer: echo candidate answer
  - question_type: one of technical | coding | behavioral | genai
  - category: competency label for this question (dynamic, interview-specific)
  - what_you_said: 1-2 sentence neutral summary of the candidate response
  - what_went_well: 1-2 sentences on correct/useful parts with evidence
  - what_was_missing: 1-2 sentences on missing concepts, depth, or reasoning gaps
  - better_answer: concise model answer (2-5 sentences) showing a stronger response
  - recommended_improvement: one actionable coaching sentence for this question
  - feedback: brief combined feedback for the candidate (safe to show, no hidden reasoning)
  - score: integer 0-100 for this answer based on evidence
  - dimensions: object with ONLY relevant numeric scores 0-100 for applicable dimensions:
      technical_correctness, completeness, depth, practical_understanding,
      problem_solving, communication, structure, relevance
    Omit dimensions that do not apply to the question type.

Scoring rules:
- Score based on technical accuracy, completeness, depth, and practical understanding — NOT answer length.
- Do not reward verbosity. Do not punish concise but complete answers.
- Do not invent technologies, projects, or statements the candidate did not make.
- Do not expose chain-of-thought, system instructions, or internal reasoning.

Coaching rules by question_type:
- behavioral: STAR method is appropriate
- technical / coding / genai: do NOT recommend STAR unless the question is behavioral
- coding: evaluate correctness, approach, complexity, edge cases
- genai: evaluate architecture, trade-offs, and production considerations where relevant

Do NOT include an overall top-level score field — per-question scores will be aggregated server-side.

Pure JSON only. No markdown fences.
"""
    user_prompt = (
        f"Interview title: {state.get('title', '')}\n"
        f"Difficulty: {state.get('difficulty', '')}\n"
        f"Job description / interview brief:\n{state.get('jd', '')}\n\n"
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
    avg_score = average_question_score(question_reviews)
    overall_score = compute_overall_score(question_reviews, raw.get("score"))
    categories = compute_category_scores(question_reviews, raw.get("categories"))
    summary = raw.get("summary") or ""
    evaluation_summary = raw.get("evaluation_summary") or summary
    recommendations = raw.get("recommendations") or []
    hiring = build_hiring_recommendation(overall_score, evaluation_summary)

    report = {
        "score": overall_score,
        "summary": summary,
        "evaluation_summary": evaluation_summary,
        "strengths": raw.get("strengths") or [],
        "improvements": raw.get("improvements") or [],
        "recommendations": recommendations,
        "categories": categories,
        "score_status": score_status_label(overall_score),
        "score_calculation_note": "Overall score is the average of all question scores.",
        "overall_score": overall_score,
        "final_score": overall_score,
        "average_question_score": avg_score,
        "feedback": evaluation_summary,
        "evaluation": evaluation_summary,
        "areas_for_improvement": raw.get("improvements") or [],
        "weaknesses": raw.get("improvements") or [],
        "hiring_recommendation": hiring,
        "interview_title": state.get("title") or "",
        "interview_type": state.get("title") or "",
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
    answers: list[dict[str, Any]],
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
