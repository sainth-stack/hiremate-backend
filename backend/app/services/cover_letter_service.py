"""Cover letter generation from user profile + job description."""
from openai import OpenAI

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from backend.app.schemas.profile import ProfilePayload, profile_model_to_payload
from backend.app.services.profile_service import build_resume_text_from_payload

logger = get_logger("services.cover_letter")

COVER_LETTER_PROMPT = """Write a professional cover letter (2-3 paragraphs) for this job application.
Use ONLY facts from the candidate's profile. Do not invent experience or skills.
Highlight relevant experience and why the candidate is a good fit for the role.
Keep it concise and professional. Output ONLY the cover letter text, no greetings or sign-offs.
If the job description is empty, write a general professional cover letter based on the profile.

Candidate profile summary:
{profile_summary}

Resume text (excerpt):
{resume_excerpt}

Job title: {job_title}
Job description: {job_description}
"""


def generate_cover_letter(
    payload: ProfilePayload,
    job_title: str = "",
    job_description: str = "",
) -> str | None:
    """Generate cover letter using LLM. Returns text or None on failure."""
    if not settings.openai_api_key:
        return None
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        resume_text = build_resume_text_from_payload(payload)
        name = f"{payload.firstName or ''} {payload.lastName or ''}".strip() or "the candidate"
        headline = payload.professionalHeadline or ""
        summary = (payload.professionalSummary or "")[:400]
        profile_summary = f"Name: {name}. Headline: {headline}. Summary: {summary}"
        resume_excerpt = (resume_text or "")[:800]
        job_title = (job_title or "").strip() or "the position"
        job_description = (job_description or "").strip()[:1500] or "General application."

        prompt = COVER_LETTER_PROMPT.format(
            profile_summary=profile_summary,
            resume_excerpt=resume_excerpt,
            job_title=job_title,
            job_description=job_description,
        )
        resp = client.chat.completions.create(
            model=getattr(settings, "openai_model", "gpt-4o-mini") or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=600,
        )
        content = (resp.choices[0].message.content or "").strip()
        if content and len(content) > 50:
            return content[:2500]
    except Exception as e:
        logger.warning("Cover letter generation failed: %s", e)
    return None
