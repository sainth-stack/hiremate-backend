"""Per-section AI generation with SSE streaming support."""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from openai import OpenAI

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

SECTION_PROMPTS: dict[str, str] = {
    "summary": (
        "You are an expert resume writer. Write a compelling professional summary for this candidate.\n\n"
        "Candidate Profile: {profile_basics}\n"
        "Target Job Description: {jd}\n"
        "Tone: {tone}\n\n"
        "Rules:\n"
        "- 3-4 sentences maximum\n"
        "- Lead with years of experience and core expertise\n"
        "- Mirror 2-3 key terms from the JD naturally\n"
        "- End with a value proposition statement\n"
        "- NO first-person pronouns (no 'I', 'my', 'me')\n"
        "- Output only the summary text, no labels or formatting"
    ),
    "skills": (
        "Extract and organize skills for this resume.\n\n"
        "Candidate's Current Skills: {current_skills}\n"
        "Job Description Keywords: {jd}\n\n"
        "Rules:\n"
        "- Group into: Technical Skills | Tools & Platforms | Soft Skills\n"
        "- Prioritize skills that appear in the JD\n"
        "- Add 2-3 relevant skills the candidate likely has based on experience\n"
        "- Format: Category: skill1, skill2, skill3\n"
        "- Maximum 5 skills per category"
    ),
    "experience_bullet": (
        "Rewrite this experience bullet point to be more impactful.\n\n"
        "Original bullet: \"{original_bullet}\"\n"
        "Role: {role_title}\n"
        "Company: {company}\n"
        "JD context: {jd_snippet}\n"
        "{user_instruction}\n\n"
        "Rules:\n"
        "- Start with a strong action verb (Led, Built, Reduced, Increased, Delivered...)\n"
        "- Include ONE quantified metric if possible (%, $, time saved, users, etc.)\n"
        "- One line max - 15-20 words ideal\n"
        "- Mirror relevant JD language naturally\n"
        "- Output only the rewritten bullet, no labels"
    ),
}


def _build_prompt(
    section: str,
    profile: dict,
    jd: str,
    tone: str | None,
    context: dict | None,
) -> str:
    template = SECTION_PROMPTS.get(section)
    if not template:
        raise ValueError(f"Unknown section: {section!r}. Valid: {list(SECTION_PROMPTS)}")

    basics = profile.get("basics", {})
    # Flatten basics from top-level profile keys if nested "basics" key is absent
    if not basics:
        basics = {
            k: profile.get(k, "")
            for k in ("firstName", "lastName", "professionalHeadline", "city", "country")
        }

    tech_skills = profile.get("techSkills", [])
    if tech_skills and isinstance(tech_skills[0], dict):
        skill_names = [s.get("name", "") for s in tech_skills if s.get("name")]
    else:
        skill_names = [str(s) for s in tech_skills if s]

    ctx: dict[str, str] = {
        "profile_basics": json.dumps(basics, ensure_ascii=False),
        "current_skills": ", ".join(skill_names),
        "jd": jd[:1000],
        "jd_snippet": jd[:500],
        "tone": tone or "professional",
        "original_bullet": (context or {}).get("instruction", ""),
        "role_title": "",
        "company": "",
        "user_instruction": (
            f"User instruction: {context['instruction']}"
            if context and context.get("instruction")
            else ""
        ),
    }

    if section == "experience_bullet" and context:
        role_index = context.get("role_index", 0)
        experiences = profile.get("experiences", [])
        if isinstance(role_index, int) and role_index < len(experiences):
            role = experiences[role_index]
            ctx["role_title"] = role.get("jobTitle", "")
            ctx["company"] = role.get("companyName", "")

    return template.format(**ctx)


async def generate_section_stream(
    section: str,
    profile: dict,
    jd: str,
    tone: str | None = None,
    context: dict | None = None,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted tokens for a resume section generation request."""
    if not settings.openai_api_key:
        yield f"data: {json.dumps({'error': 'OpenAI API key not configured'})}\n\n"
        return

    try:
        prompt = _build_prompt(section, profile, jd, tone, context)
    except ValueError as exc:
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        return

    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.openai_model or "gpt-4o"

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            max_tokens=600,
            temperature=0.7,
        )

        full_content = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_content += delta
                yield f"data: {json.dumps({'delta': delta})}\n\n"

        word_count = len(full_content.split())
        yield f"data: {json.dumps({'done': True, 'full_content': full_content, 'word_count': word_count})}\n\n"

    except Exception as exc:
        logger.exception("Section generation stream failed section=%s", section)
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"


def generate_section_sync(
    section: str,
    profile: dict,
    jd: str,
    tone: str | None = None,
    context: dict | None = None,
) -> str:
    """Non-streaming fallback — returns the full generated text."""
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key not configured")

    prompt = _build_prompt(section, profile, jd, tone, context)
    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.openai_model or "gpt-4o"

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.7,
    )
    return response.choices[0].message.content or ""
