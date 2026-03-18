"""
Optional LLM-powered resume analysis for ATS scan and Resume Analyze.
When OPENAI_API_KEY is set, enriches reports with AI-generated improvement suggestions and insights.
"""
import json
import re

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger

logger = get_logger("services.resume_analysis_llm")


def _get_llm():
    """Return ChatOpenAI instance if API key is set, else None."""
    if not (getattr(settings, "openai_api_key", None) or "").strip():
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=getattr(settings, "openai_model", "gpt-4o-mini") or "gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.3,
        )
    except Exception as e:
        logger.warning("Resume analysis LLM init failed: %s", e)
        return None


def get_ats_improvements(resume_text: str, job_description: str) -> list[dict] | None:
    """
    Use LLM to generate ATS-focused improvement suggestions (recruiter tips).
    Returns list of { "label": str, "items": [ {"status": "warn"|"fail"|"pass", "text": str} ] } or None.
    """
    llm = _get_llm()
    if not llm:
        return None
    resume_preview = (resume_text or "")[:4000]
    jd_preview = (job_description or "")[:3000]
    prompt = f"""You are an ATS (Applicant Tracking System) and resume expert. Given a resume and a job description, suggest 2-4 specific improvements or checks for the candidate.

Resume (excerpt):
{resume_preview}

Job description (excerpt):
{jd_preview}

Respond with a JSON array only, no markdown. Each element: {{ "label": "Short category name", "items": [ {{ "status": "pass" or "warn" or "fail", "text": "One sentence explanation" }} ] }}
Example: [{{ "label": "Keyword match", "items": [{{ "status": "warn", "text": "Add the term 'React' from the job description to your skills section." }}] }}]
"""
    try:
        resp = llm.invoke(prompt)
        content = (resp.content or "").strip()
        # Strip markdown code block if present
        if content.startswith("```"):
            content = re.sub(r"^```\w*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)
        data = json.loads(content)
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception as e:
        logger.warning("ATS LLM improvements failed: %s", e)
    return None


def get_resume_insights(resume_text: str) -> dict | None:
    """
    Use LLM to generate resume analysis: issues to fix and what was done well.
    Returns { "issues": [ { "icon": "cancel", "title": str, "desc": str, "badge": str, "locked": false } ], "did_well": [ { "title": str, "desc": str } ] } or None.
    """
    llm = _get_llm()
    if not llm:
        return None
    resume_preview = (resume_text or "")[:5000]
    prompt = f"""You are a professional resume reviewer. Analyze this resume and respond with JSON only (no markdown).

Resume (excerpt):
{resume_preview}

Respond with exactly this structure (JSON object):
{{ "issues": [ {{ "icon": "cancel", "title": "Short title", "desc": "One sentence actionable advice", "badge": "IMPACT or SKILLS", "locked": false }} ], "did_well": [ {{ "title": "Short title", "desc": "One sentence positive finding" }} ] }}
Provide 2-4 issues and 2-3 did_well items. Keep titles and text concise.
"""
    try:
        resp = llm.invoke(prompt)
        content = (resp.content or "").strip()
        if content.startswith("```"):
            content = re.sub(r"^```\w*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)
        data = json.loads(content)
        if isinstance(data, dict) and ("issues" in data or "did_well" in data):
            return data
    except Exception as e:
        logger.warning("Resume insights LLM failed: %s", e)
    return None
