from backend.jobradar.services.llm_factory import LLMFactory
from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from backend.app.schemas.profile import ProfilePayload
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
    user_id: int = None,
    email: str = None,
) -> str | None:
    """Generate cover letter using LLM. Returns text or None on failure."""
    if not settings.openai_api_key:
        return None
    try:
        provider = LLMFactory.get_provider()
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
        
        content = provider.generate(
            system_prompt="",
            user_prompt=prompt,
            user_id=user_id,
            email=email,
            feature="cover_letter_gen",
            max_tokens=600,
            temperature=0.5
        )
        
        content = (content or "").strip()
        if content and len(content) > 50:
            return content[:2500]
    except Exception as e:
        logger.warning("Cover letter generation failed: %s", e)
    return None
