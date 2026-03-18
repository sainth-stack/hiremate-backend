"""
ATS Scan endpoint - resume + job description -> ATS score and report.
"""
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.app.core.dependencies import get_current_user
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.services.resume_analysis_llm import get_ats_improvements
from backend.app.services.resume_extractor.pdf_utils import extract_text_from_pdf

logger = get_logger("api.resume.ats_scan")
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _extract_keywords(text: str, min_len: int = 3) -> set:
    """Extract normalized words (potential keywords) from text."""
    text = (text or "").lower()
    words = re.findall(r"[a-z0-9+.#]+", text)
    return {w for w in words if len(w) >= min_len and w not in {"the", "and", "for", "with", "from", "this", "that"}}


def _build_ats_report(resume_text: str, job_description: str, file_name: str) -> dict:
    """Build ATS scan report from resume and job description text."""
    resume_words = _extract_keywords(resume_text)
    job_words = _extract_keywords(job_description)
    if not job_words:
        match_pct = 0
        matched_skills = []
    else:
        matched = resume_words & job_words
        match_pct = min(100, round(100 * len(matched) / len(job_words)))
        matched_skills = sorted(matched)[:30]

    # Category scores (simplified: derive from match and length)
    word_count = len(resume_text.split())
    searchability = min(100, match_pct + 20) if "email" in resume_text.lower() else min(80, match_pct + 10)
    hard_skills = match_pct
    soft_skills = min(100, 40 + (match_pct // 2))
    recruiter_tips = min(100, 30 + (word_count // 15))
    formatting = 75 if word_count < 1500 and "experience" in resume_text.lower() else 60

    score_categories = [
        {"label": "Searchability", "issues": 5 if searchability < 50 else 0, "value": searchability, "color": "var(--primary)"},
        {"label": "Hard Skills", "issues": 8 if hard_skills < 40 else 0, "value": hard_skills, "color": "var(--error)" if hard_skills < 40 else "var(--primary)"},
        {"label": "Soft Skills", "issues": 1 if soft_skills < 50 else 0, "value": soft_skills, "color": "var(--primary)"},
        {"label": "Recruiter Tips", "issues": 3 if recruiter_tips < 50 else 0, "value": recruiter_tips, "color": "var(--primary)"},
        {"label": "Formatting", "issues": 0, "value": formatting, "color": "var(--primary)"},
    ]

    # Searchability-style rows (simplified)
    has_email = "@" in resume_text
    has_phone = bool(re.search(r"[\d\s\-+()]{10,}", resume_text))
    has_summary = "summary" in resume_text.lower() or "objective" in resume_text.lower()
    searchability_rows = [
        {
            "label": "Contact Information",
            "items": [
                {"status": "pass" if has_email else "fail", "text": "You provided your email." if has_email else "We did not find an email in your resume."},
                {"status": "pass" if has_phone else "fail", "text": "You provided your phone number." if has_phone else "We did not find a phone number."},
            ],
        },
        {
            "label": "Summary",
            "items": [{"status": "pass" if has_summary else "warn", "text": "We found a summary section." if has_summary else "Consider adding a summary section."}],
        },
    ]

    # Hard/soft skills rows (from matched keywords)
    hard_skills_rows = [{"skill": s, "inResume": True, "count": 1, "locked": False} for s in matched_skills[:12]]
    soft_skills_rows = [{"skill": "Communication", "inResume": "communication" in resume_text.lower(), "count": 1, "locked": False}]

    # Recruiter tips
    recruiter_tips_rows = [
        {"label": "Measurable Results", "items": [{"status": "warn" if resume_text.count("%") < 2 else "pass", "text": "Consider adding more measurable results (numbers, percentages)."}]},
        {"label": "Word Count", "items": [{"status": "pass", "text": f"Your resume has approximately {word_count} words."}]},
    ]

    # Formatting
    formatting_rows = [
        {"label": "Layout", "items": [{"status": "pass", "text": "Resume length appears reasonable."}]},
    ]

    return {
        "score": match_pct,
        "file_name": file_name,
        "score_categories": score_categories,
        "searchability_rows": searchability_rows,
        "hard_skills_rows": hard_skills_rows,
        "soft_skills_rows": soft_skills_rows,
        "recruiter_tips_rows": recruiter_tips_rows,
        "formatting_rows": formatting_rows,
        "job_description_preview": (job_description or "")[:500],
    }


@router.post("/ats-scan")
async def ats_scan(
    file: UploadFile = File(...),
    job_description: str = Form(""),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    ATS Scan: upload resume (PDF) + job description, get ATS score and report.
    Returns score, categories, and check rows for the scan report UI.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF is supported for ATS scan. Please upload a PDF resume.",
        )
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")
    if len((job_description or "").strip()) < 50:
        raise HTTPException(status_code=400, detail="Please provide at least 50 characters of job description.")

    file_name = file.filename or "resume.pdf"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        resume_text = extract_text_from_pdf(tmp_path)
    except Exception as e:
        logger.warning("ATS scan PDF extraction failed: %s", e)
        raise HTTPException(status_code=400, detail="Could not read PDF. Ensure it is a valid PDF with extractable text.") from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not (resume_text or "").strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from the PDF.")

    report = _build_ats_report(resume_text.strip(), (job_description or "").strip(), file_name)
    # Optional LLM enrichment for recruiter tips
    try:
        llm_tips = get_ats_improvements(resume_text.strip(), (job_description or "").strip())
        if llm_tips and isinstance(llm_tips, list):
            report["recruiter_tips_rows"] = report.get("recruiter_tips_rows", []) + llm_tips
            logger.info("ATS scan enriched with LLM tips user_id=%s", current_user.id)
    except Exception as e:
        logger.warning("ATS LLM enrichment skipped: %s", e)
    logger.info("ATS scan completed user_id=%s score=%s", current_user.id, report["score"])
    return report
