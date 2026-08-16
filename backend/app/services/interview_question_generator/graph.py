"""LangGraph pipeline: description -> difficulty-mixed question cards."""
from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from backend.jobradar.services.classifier import InterviewQuestionData
from backend.jobradar.services.llm_factory import LLMFactory
from backend.app.services.interview_question_generator.constants import (
    BEHAVIORAL_QUESTION_PATTERNS,
    NON_TECHNICAL_CATEGORY_MARKERS,
    TECHNICAL_COMPLEXITY_GUIDE,
    TEMPLATE_BY_COMPLEXITY,
    TIME_CARD_BY_COMPLEXITY,
    TOTAL_QUESTIONS,
    get_difficulty_mix,
    normalize_difficulty,
)
from backend.app.services.interview_question_generator.question_count import resolve_question_count
from backend.app.services.interview_question_generator.state import (
    MAX_GENERATION_RETRIES,
    InterviewQuestionGenerationState,
)

logger = logging.getLogger(__name__)


def _get_total_questions(state: InterviewQuestionGenerationState) -> int:
    total = int(state.get("total_questions") or TOTAL_QUESTIONS)
    return max(3, min(total, 30))


def _generation_buffer(total: int) -> int:
    return min(5, max(3, total // 5))


def _parse_json_list(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    data = json.loads(text)
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                return value
        return []
    return data if isinstance(data, list) else []


def _normalize_complexity(value: str) -> str:
    v = (value or "medium").strip().lower()
    if v in {"easy", "medium", "hard"}:
        return v
    return "medium"


def _is_non_technical_question(question_text: str, category: str) -> bool:
    text = question_text.strip().lower()
    cat = category.strip().lower()
    if any(marker in cat for marker in NON_TECHNICAL_CATEGORY_MARKERS):
        return True
    return any(pattern in text for pattern in BEHAVIORAL_QUESTION_PATTERNS)


def _fallback_skills_from_description(description: str) -> list[str]:
    parts = [
        part.strip()
        for part in description.replace("\n", ",").split(",")
        if part.strip()
    ]
    return parts[:12] if parts else ["General Programming"]


def _parse_skills_list(raw: str) -> list[str]:
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return _fallback_skills_from_description(text)

    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]
    if isinstance(data, dict):
        for key in ("skills", "technical_skills", "technologies"):
            value = data.get(key)
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
    return _fallback_skills_from_description(raw)


def _coerce_question_item(item: Any) -> dict[str, Any] | None:
    """Leniently normalize LLM output before strict validation."""
    if not isinstance(item, dict):
        return None

    question_text = (
        item.get("question_text")
        or item.get("question")
        or item.get("text")
        or ""
    )
    if isinstance(question_text, str):
        question_text = question_text.strip()
    else:
        question_text = str(question_text).strip()
    if not question_text:
        return None

    category = (item.get("category") or item.get("type") or "Technical")
    if isinstance(category, str):
        category = category.strip() or "Technical"
    else:
        category = str(category)
    category = "Technical"

    skill = (item.get("skill") or item.get("technology") or item.get("topic") or "").strip()

    expectations = item.get("expectations") or item.get("criteria") or []
    if isinstance(expectations, str):
        expectations = [
            part.strip(" •-\t")
            for part in expectations.replace(";", "\n").split("\n")
            if part.strip(" •-\t")
        ]
    elif not isinstance(expectations, list):
        expectations = [str(expectations)]

    star = item.get("star_breakdown") or item.get("star") or {"s": False, "t": False, "a": False, "r": False}
    if not isinstance(star, dict):
        star = {"s": True, "t": True, "a": True, "r": True}

    complexity = item.get("complexity") or item.get("difficulty") or "Medium"
    duration = item.get("duration") or item.get("time") or ""

    return {
        "category": category,
        "skill": skill,
        "question_text": question_text,
        "overview": item.get("overview") or item.get("context") or "",
        "intent": item.get("intent") or item.get("purpose") or "",
        "expectations": expectations,
        "sample_answer": item.get("sample_answer") or item.get("answer") or "",
        "star_breakdown": star,
        "complexity": complexity,
        "duration": duration,
    }


def _validate_question_item(item: dict[str, Any]) -> dict[str, Any] | None:
    coerced = _coerce_question_item(item)
    if not coerced:
        return None
    try:
        q = InterviewQuestionData(**coerced)
    except ValidationError as exc:
        logger.warning("Skipping invalid generated question: %s", exc)
        return None

    if _is_non_technical_question(coerced["question_text"], coerced["category"]):
        logger.warning("Skipping non-technical question: %s", coerced["question_text"][:80])
        return None

    complexity = _normalize_complexity(q.complexity)
    return {
        "category": "Technical",
        "skill": coerced.get("skill") or "",
        "question_text": q.question_text,
        "overview": q.overview or "",
        "intent": q.intent or "",
        "expectations": q.expectations or [],
        "sample_answer": q.sample_answer or "",
        "star_breakdown": q.star_breakdown or {"s": False, "t": False, "a": False, "r": False},
        "complexity": complexity,
        "duration": q.duration or TIME_CARD_BY_COMPLEXITY[complexity]["duration"],
    }


def _merge_validated(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen = {q["question_text"].strip().lower() for q in existing}
    merged = list(existing)
    for q in incoming:
        key = q["question_text"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(q)
    return merged


def _build_generation_prompt(
    *,
    count: int,
    mix: dict[str, int],
    title: str,
    difficulty: str,
    description: str,
    technical_skills: list[str],
    existing_questions: list[str] | None = None,
) -> tuple[str, str]:
    avoid_clause = ""
    if existing_questions:
        listed = "\n".join(f"- {q}" for q in existing_questions[:20])
        avoid_clause = f"\nDo NOT repeat or paraphrase these existing questions:\n{listed}\n"

    skills_list = ", ".join(technical_skills) if technical_skills else description
    skills_distribution = (
        "Distribute questions across ALL listed skills. "
        "Each question must target exactly one primary skill."
    )

    system_prompt = f"""
You are an experienced human technical interviewer preparing questions for a live voice interview.

Return ONLY a JSON array of exactly {count} objects.

CONVERSATIONAL STYLE (how a real interviewer speaks):
- Phrase each question naturally, as spoken in a 1:1 interview — not like an exam rubric
- Prefer "Can you walk me through...", "How would you...", "What happens when..." over "Define X" or "Explain X"
- One focused question per item; avoid stacking multiple sub-questions in one sentence
- For scenarios: give 1–2 sentences of context, then ask one clear question
- Keep question_text concise (ideally under 45 words) and easy to read aloud
- Do NOT copy bullet lists, section headers, or markdown from the job description verbatim
- Match topics and depth to the role description, but rewrite in your own words

STRICT RULES — TECHNICAL ONLY:
- category MUST always be "Technical" for every question
- DO NOT generate Behavioral, HR, Culture, soft-skill, or project-management questions
- DO NOT ask "describe a time when...", teamwork, conflict, or career-motivation questions
- Every question must test a specific technical skill from the job description
- Questions must be answerable with technical knowledge (concepts, code, architecture, debugging)

Target complexity mix (complexity field: Easy, Medium, or Hard):
- Easy ({mix["easy"]} questions): {TECHNICAL_COMPLEXITY_GUIDE["easy"]}
- Medium ({mix["medium"]} questions): {TECHNICAL_COMPLEXITY_GUIDE["medium"]}
- Hard ({mix["hard"]} questions): {TECHNICAL_COMPLEXITY_GUIDE["hard"]}

Each object must include:
- category: always "Technical"
- skill: the primary technical skill being tested (e.g. "React", "Node.js", "MongoDB")
- question_text: technical interview question (non-empty string)
- overview: one sentence — what technical concept this tests
- intent: what technical ability is being evaluated
- expectations: array of exactly 3 technical evaluation criteria
- sample_answer: concise model technical answer with examples where relevant
- star_breakdown: object with keys s,t,a,r as booleans (all false for technical questions)
- complexity: Easy | Medium | Hard
- duration: "2-3 min" for Easy, "3-5 min" for Medium, "5-7 min" for Hard

{skills_distribution}
No duplicate questions. Pure JSON only. No markdown fences.
{avoid_clause}
"""
    user_prompt = (
        f"Interview title: {title}\n"
        f"Overall interview difficulty: {difficulty}\n"
        f"Technical skills to assess:\n{skills_list}\n\n"
        f"Full job description:\n{description}"
    )
    return system_prompt, user_prompt


def _call_llm_for_questions(
    state: InterviewQuestionGenerationState,
    count: int,
    existing_questions: list[str] | None = None,
) -> list[dict[str, Any]]:
    mix = state["difficulty_mix"]
    system_prompt, user_prompt = _build_generation_prompt(
        count=count,
        mix=mix,
        title=state["title"],
        difficulty=state["difficulty"],
        description=state["description"],
        technical_skills=state.get("technical_skills") or [],
        existing_questions=existing_questions,
    )
    llm = LLMFactory.get_provider()
    raw = llm.generate(
        system_prompt,
        user_prompt,
        user_id=state.get("user_id"),
        email=state.get("email"),
        feature="admin_interview_questions",
    )
    return _parse_json_list(raw)


def prepare_plan_node(state: InterviewQuestionGenerationState) -> InterviewQuestionGenerationState:
    difficulty = normalize_difficulty(state.get("difficulty", "medium"))
    total = int(state.get("total_questions") or TOTAL_QUESTIONS)
    total = max(3, min(total, 30))
    return {
        **state,
        "difficulty": difficulty,
        "total_questions": total,
        "difficulty_mix": get_difficulty_mix(difficulty, total),
        "technical_skills": [],
        "raw_questions": [],
        "validated_questions": [],
        "questions": [],
        "retry_count": 0,
        "error": None,
    }


def extract_skills_node(state: InterviewQuestionGenerationState) -> InterviewQuestionGenerationState:
    if state.get("error"):
        return state

    description = state.get("description", "")
    system_prompt = """
Extract technical skills and technologies from the job description.
Return ONLY a JSON array of skill name strings (e.g. ["React", "Node.js", "MongoDB", "TypeScript"]).
Include frameworks, languages, databases, tools, and platforms mentioned or implied.
Exclude soft skills. No markdown fences.
"""
    user_prompt = f"Job title: {state.get('title', '')}\nDescription:\n{description}"

    try:
        llm = LLMFactory.get_provider()
        raw = llm.generate(
            system_prompt,
            user_prompt,
            user_id=state.get("user_id"),
            email=state.get("email"),
            feature="admin_interview_skill_extract",
        )
        skills = _parse_skills_list(raw)
        if not skills:
            skills = _fallback_skills_from_description(description)
        logger.info("Extracted %d technical skills: %s", len(skills), ", ".join(skills[:8]))
        return {**state, "technical_skills": skills, "error": None}
    except Exception as exc:
        logger.warning("Skill extraction failed, using fallback: %s", exc)
        return {
            **state,
            "technical_skills": _fallback_skills_from_description(description),
            "error": None,
        }


def generate_questions_node(state: InterviewQuestionGenerationState) -> InterviewQuestionGenerationState:
    try:
        total = _get_total_questions(state)
        # Request a small buffer — some items may fail coercion/validation.
        raw_questions = _call_llm_for_questions(state, total + _generation_buffer(total))
        if not raw_questions:
            return {**state, "error": "LLM returned no questions"}
        logger.info("LLM returned %d raw questions on initial generation", len(raw_questions))
        return {**state, "raw_questions": raw_questions, "error": None}
    except Exception as exc:
        logger.exception("Interview question generation failed")
        return {**state, "error": str(exc)}


def fill_missing_questions_node(state: InterviewQuestionGenerationState) -> InterviewQuestionGenerationState:
    total = _get_total_questions(state)
    validated = state.get("validated_questions") or []
    missing = total - len(validated)
    if missing <= 0:
        return {**state, "error": None}

    retry_count = state.get("retry_count", 0) + 1
    existing_texts = [q["question_text"] for q in validated]

    try:
        raw_questions = _call_llm_for_questions(
            state,
            missing,
            existing_questions=existing_texts,
        )
        logger.info(
            "Fill-missing attempt %d: need %d, LLM returned %d",
            retry_count,
            missing,
            len(raw_questions),
        )
        if not raw_questions:
            return {
                **state,
                "retry_count": retry_count,
                "error": f"Expected {total} valid questions, got {len(validated)}",
            }
        return {
            **state,
            "raw_questions": raw_questions,
            "retry_count": retry_count,
            "error": None,
        }
    except Exception as exc:
        logger.exception("Fill-missing question generation failed")
        return {
            **state,
            "retry_count": retry_count,
            "error": str(exc),
        }


def validate_questions_node(state: InterviewQuestionGenerationState) -> InterviewQuestionGenerationState:
    if state.get("error"):
        return state

    total = _get_total_questions(state)
    validated = list(state.get("validated_questions") or [])
    for item in state.get("raw_questions", []):
        parsed = _validate_question_item(item)
        if parsed:
            validated = _merge_validated(validated, [parsed])

    validated = validated[:total]
    logger.info("Validated %d / %d questions", len(validated), total)

    if len(validated) >= total:
        return {
            **state,
            "validated_questions": validated[:total],
            "raw_questions": validated[:total],
            "error": None,
        }

    retry_count = state.get("retry_count", 0)
    if retry_count < MAX_GENERATION_RETRIES:
        return {
            **state,
            "validated_questions": validated,
            "raw_questions": [],
            "error": None,
        }

    return {
        **state,
        "validated_questions": validated,
        "error": f"Expected {total} valid questions, got {len(validated)}",
    }


def format_card_templates_node(state: InterviewQuestionGenerationState) -> InterviewQuestionGenerationState:
    if state.get("error"):
        return state

    total = _get_total_questions(state)
    source = state.get("validated_questions") or state.get("raw_questions") or []
    cards: list[dict[str, Any]] = []
    for index, q in enumerate(source[:total], start=1):
        complexity = _normalize_complexity(q["complexity"])
        time_card = {
            **TIME_CARD_BY_COMPLEXITY[complexity],
            "duration": q.get("duration") or TIME_CARD_BY_COMPLEXITY[complexity]["duration"],
        }
        view_card = {
            "template": TEMPLATE_BY_COMPLEXITY[complexity],
            "category": "Technical",
            "skill": q.get("skill") or "",
            "overview": q["overview"],
            "intent": q["intent"],
            "question_text": q["question_text"],
        }
        cards.append(
            {
                "order": index,
                "template": TEMPLATE_BY_COMPLEXITY[complexity],
                "view_card": view_card,
                "time_card": time_card,
                "category": "Technical",
                "question_text": q["question_text"],
                "overview": q["overview"],
                "intent": q["intent"],
                "expectations": q["expectations"],
                "sample_answer": q["sample_answer"],
                "star_breakdown": q["star_breakdown"],
                "complexity": complexity,
                "duration": time_card["duration"],
            }
        )

    return {**state, "questions": cards, "error": None}


def _route_on_llm_error(state: InterviewQuestionGenerationState) -> str:
    if state.get("error"):
        return "__end__"
    return "next"


def _route_after_validate(state: InterviewQuestionGenerationState) -> str:
    if state.get("error"):
        return "__end__"
    total = _get_total_questions(state)
    validated = state.get("validated_questions") or []
    if len(validated) >= total:
        return "format"
    if state.get("retry_count", 0) < MAX_GENERATION_RETRIES:
        return "fill_missing"
    return "__end__"


def _build_graph():
    builder = StateGraph(InterviewQuestionGenerationState)
    builder.add_node("prepare_plan", prepare_plan_node)
    builder.add_node("extract_skills", extract_skills_node)
    builder.add_node("generate_questions", generate_questions_node)
    builder.add_node("fill_missing_questions", fill_missing_questions_node)
    builder.add_node("validate_questions", validate_questions_node)
    builder.add_node("format_card_templates", format_card_templates_node)

    builder.add_edge(START, "prepare_plan")
    builder.add_edge("prepare_plan", "extract_skills")
    builder.add_edge("extract_skills", "generate_questions")
    builder.add_conditional_edges(
        "generate_questions",
        _route_on_llm_error,
        {"next": "validate_questions", "__end__": END},
    )
    builder.add_conditional_edges(
        "validate_questions",
        _route_after_validate,
        {"format": "format_card_templates", "fill_missing": "fill_missing_questions", "__end__": END},
    )
    builder.add_conditional_edges(
        "fill_missing_questions",
        _route_on_llm_error,
        {"next": "validate_questions", "__end__": END},
    )
    builder.add_edge("format_card_templates", END)
    return builder.compile()


_GRAPH = None


def generate_interview_questions(
    *,
    title: str,
    description: str,
    difficulty: str,
    user_id: int | None = None,
    email: str | None = None,
    question_count: int = TOTAL_QUESTIONS,
) -> list[dict[str, Any]]:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()

    count = resolve_question_count(question_count, description)
    initial: InterviewQuestionGenerationState = {
        "title": title.strip(),
        "description": description.strip(),
        "difficulty": difficulty,
        "user_id": user_id,
        "email": email,
        "total_questions": count,
        "difficulty_mix": {},
        "technical_skills": [],
        "raw_questions": [],
        "validated_questions": [],
        "questions": [],
        "retry_count": 0,
        "error": None,
    }
    result = _GRAPH.invoke(initial)
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result.get("questions", [])
