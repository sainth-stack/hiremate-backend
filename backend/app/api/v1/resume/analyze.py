"""
Resume Analyze endpoint - upload resume, get deep insights (strengths, gaps, fixes).
"""
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.core.dependencies import get_current_user
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.services.resume_analysis_llm import get_resume_insights
from backend.app.services.resume_extractor.pdf_utils import extract_text_from_pdf

logger = get_logger("api.resume.analyze")
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _build_analyze_report(resume_text: str, file_name: str) -> dict:
    """Build resume analysis report for the score/insights UI."""
    text_lower = (resume_text or "").lower()
    word_count = len((resume_text or "").split())

    # Simple score from basic checks
    score = 40
    if "experience" in text_lower or "work" in text_lower:
        score += 15
    if "education" in text_lower or "degree" in text_lower:
        score += 10
    if "skill" in text_lower or "technical" in text_lower:
        score += 10
    if "@" in resume_text:
        score += 5
    if re.search(r"[\d\s\-+()]{10,}", resume_text):
        score += 5
    if word_count >= 200:
        score += 5
    if "%" in resume_text or "increased" in text_lower or "reduced" in text_lower:
        score += 10
    score = min(100, score)

    top_fixes = [
        {"label": "Quantify impact", "count": 3, "locked": False},
        {"label": "Repetition", "count": 2, "locked": False},
        {"label": "Leadership & ownership", "count": 2, "locked": False},
        {"label": "Use of bullets", "count": 4, "locked": False},
        {"label": "Communication clarity", "count": 2, "locked": False},
    ]
    completed = [
        {"label": "Buzzwords", "count": 10},
        {"label": "Dates", "count": 10},
        {"label": "Unnecessary sentences", "count": 10},
    ]
    issues = [
        {"icon": "cancel", "title": "Quantify impact", "desc": "Add metrics and numbers to quantify your accomplishments.", "badge": "IMPACT", "locked": False},
        {"icon": "cancel", "title": "Repetition", "desc": "Vary action verbs and phrasing so bullets do not sound repetitive.", "badge": "IMPACT", "locked": False},
        {
            "icon": "cancel",
            "title": "Leadership & collaboration",
            "desc": "Surface examples of leading initiatives, mentoring, or cross-functional work.",
            "badge": "SKILLS",
            "locked": False,
        },
    ]
    did_well = [
        {"title": "Page density", "desc": "Your page layout looks right."},
        {"title": "Dates format", "desc": "Your dates are in a clear format."},
        {"title": "Verb tenses", "desc": "Your action verbs are in the right tense."},
    ]

    return {
        "score": score,
        "max_score": 100,
        "file_name": file_name,
        "top_fixes": top_fixes,
        "completed": completed,
        "issues": issues,
        "did_well": did_well,
    }


from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.services.usage_service import check_feature_limit

@router.post("/analyze")
async def analyze_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Resume Analyze: upload resume (PDF), get deep insights, top fixes, and strengths.
    Returns score, top_fixes, completed, issues, did_well for the analyze-score UI.
    """
    # Check plan limits
    allowed, message = check_feature_limit(db, current_user, "ats_match_checks")
    if not allowed:
        raise HTTPException(status_code=403, detail=message)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF is supported for resume analysis. Please upload a PDF.",
        )
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")

    file_name = file.filename or "resume.pdf"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        resume_text = extract_text_from_pdf(tmp_path)
    except Exception as e:
        logger.warning("Analyze PDF extraction failed: %s", e)
        raise HTTPException(status_code=400, detail="Could not read PDF. Ensure it is a valid PDF with extractable text.") from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not (resume_text or "").strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from the PDF.")

    report = _build_analyze_report(resume_text.strip(), file_name)
    # Optional LLM enrichment for issues and did_well
    try:
        insights = get_resume_insights(
            resume_text.strip(),
            user_id=current_user.id,
            email=current_user.email
        )
        if insights:
            if insights.get("issues") and isinstance(insights["issues"], list):
                def _issue_icon(item: dict) -> str:
                    raw = (item.get("icon") or "cancel").lower()
                    return "cancel" if raw in ("lock", "locked") else raw

                report["issues"] = [
                    {**item, "icon": _issue_icon(item), "locked": False}
                    for item in insights["issues"][:8]
                ]
            if insights.get("did_well") and isinstance(insights["did_well"], list):
                report["did_well"] = insights["did_well"][:4]
            logger.info("Resume analyze enriched with LLM insights user_id=%s", current_user.id)
    except Exception as e:
        logger.warning("Resume analyze LLM enrichment skipped: %s", e)
    logger.info("Resume analyze completed user_id=%s score=%s", current_user.id, report["score"])
    return report
