"""
Dynamic resume generation: fetch profile, match JD keywords.
Uses Jinja2 for HTML templates and WeasyPrint for HTML→PDF conversion.
Same user profile with JD optimizations (prioritized bullets by keywords).
"""
import hashlib
import html
import re
import subprocess
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

from jinja2 import Environment, BaseLoader, FileSystemLoader
from sqlalchemy.orm import Session

from backend.app.models.profile import Profile
from backend.app.models.user import User

try:
    from backend.app.models.resume_template import ResumeTemplate
except ImportError:
    ResumeTemplate = None  # Optional: LaTeX templates; HTML/WeasyPrint flow does not need it
from backend.app.models.user_resume import UserResume
from backend.app.schemas.profile import (
    Education,
    Experience,
    ProfilePayload,
    Project,
    TechSkill,
    profile_model_to_payload,
)
from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from backend.app.services.keyword_analyzer import extract_keywords_for_resume

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
from backend.app.services.profile_service import ProfileService, build_resume_text_from_payload
from backend.app.services.s3_service import upload_file_to_s3, generate_presigned_url

logger = get_logger("services.resume_generator")

# Skill name -> category mapping (case-insensitive partial match)
# Order matters: more specific terms first to avoid miscategorization
SKILL_CATEGORIES = {
    "languages": [
        "javascript", "typescript", "java", "python", "c++", "c#", "c ",
        "sql", "go", "rust", "kotlin", "swift", "ruby", "php", "r ", "scala",
    ],
    "frontend": [
        "react", "reactjs", "react.js", "angular", "vue", "next.js", "next",
        "html", "css", "sass", "tailwind", "bootstrap", "material ui", "redux",
        "jquery", "webpack", "vite",
    ],
    "backend": [
        "node.js", "nodejs", "node", "express", "django", "fastapi", "flask",
        "spring", "hibernate", "jpa", "microservices", "graphql", "rest", "jwt",
        "cypress",
    ],
    "genai": [
        "langchain", "langgraph", "openai", "chroma", "qdrant", "pinecone",
        "vector", "rag", "llm", "genai", "hugging face", "transformers",
        "ollama", "anthropic", "claude",
    ],
    "tools": [
        "git", "jira", "vs code", "postman", "figma", "firebase", "swagger",
        "android studio", "linux",
    ],
    "devops": [
        "aws", "docker", "kubernetes", "k8s", "nginx", "ci/cd", "terraform",
        "jenkins", "github actions", "azure", "gcp",
    ],
}

# Aliases for deduplication: canonical -> variants (e.g. React.js and React are same)
_SKILL_ALIASES: dict[str, set[str]] = {
    "react": {"react", "react.js", "reactjs"},
    "node": {"node", "node.js", "nodejs"},
    "javascript": {"javascript", "js"},
    "typescript": {"typescript", "ts"},
    "vue": {"vue", "vue.js", "vuejs"},
    "angular": {"angular", "angularjs", "angular.js"},
}


def _normalize_skill_for_dedup(skill: str) -> str:
    """Return canonical form for deduplication. React.js and React -> react."""
    s = (skill or "").strip().lower()
    if not s:
        return ""
    for canonical, variants in _SKILL_ALIASES.items():
        if s in variants or s == canonical:
            return canonical
    return s


def _skill_already_in_skills(skill: str, skills_dict: dict[str, str]) -> bool:
    """Check if skill (or its alias) already exists in any category."""
    norm = _normalize_skill_for_dedup(skill)
    if not norm:
        return False
    s_lower = (skill or "").strip().lower()
    for val in skills_dict.values():
        if not val:
            continue
        for existing in val.split(","):
            ex = existing.strip().lower()
            if not ex:
                continue
            if ex == s_lower:
                return True
            ex_norm = _normalize_skill_for_dedup(existing)
            if ex_norm and norm == ex_norm:
                return True
    return False


def _latex_escape(s: str) -> str:
    """Escape LaTeX special characters: \\ { } $ & # _ %"""
    if not s:
        return ""
    for char, repl in [
        ("\\", "\\textbackslash "),
        ("{", "\\{"),
        ("}", "\\}"),
        ("$", "\\$"),
        ("&", "\\&"),
        ("#", "\\#"),
        ("_", "\\_"),
        ("%", "\\%"),
    ]:
        s = s.replace(char, repl)
    return s


def _get_jd_keywords(job_description: str) -> set[str]:
    """Extract keywords from JD using same logic as extension's analyze API.
    Ensures resume targets exact keywords the analyzer will check (90%+ match)."""
    if not job_description or len((job_description or "").strip()) < 50:
        return set()
    extracted = extract_keywords_for_resume(job_description)
    high = extracted.get("high_priority") or []
    low = extracted.get("low_priority") or []
    return {k.lower().strip() for k in (high + low) if k}


def _score_bullet(bullet: str, keywords: set[str]) -> int:
    """Score how relevant a bullet is to the job description keywords."""
    if not bullet or not keywords:
        return 0
    bullet_lower = bullet.lower()
    return sum(1 for k in keywords if k in bullet_lower)


def _categorize_skills(tech_skills: list[TechSkill]) -> dict[str, str]:
    """Group tech skills into template categories. Deduplicates aliases (React/React.js)."""
    categories: dict[str, list[str]] = {
        "languages": [],
        "frontend": [],
        "backend": [],
        "genai": [],
        "tools": [],
        "devops": [],
    }
    seen_normalized = set()

    def add_to_category(skill_name: str) -> None:
        sn = skill_name.strip()
        if not sn:
            return
        norm = _normalize_skill_for_dedup(sn)
        if norm and norm in seen_normalized:
            return
        seen_normalized.add(norm or sn.lower())
        nlower = sn.lower()
        for cat, keywords in SKILL_CATEGORIES.items():
            if any(kw in nlower or nlower in kw for kw in keywords):
                if sn not in categories[cat]:
                    categories[cat].append(sn)
                return
        # Default: put in tools only if not a known tech (avoids React in tools)
        if sn not in categories["tools"]:
            categories["tools"].append(sn)

    for ts in tech_skills or []:
        add_to_category(ts.name)
    # Single-page: max 8 skills per category
    return {k: ", ".join(v[:8]) for k, v in categories.items() if v}


def _enrich_skills_with_jd_keywords(
    skills_dict: dict[str, str],
    payload,
    jd_keywords: set[str],
) -> dict[str, str]:
    """Add JD keywords to skills when they appear in profile (experiences, projects, techSkills).
    Also adds JD keywords in same category as user's skills for better match % (90%+ target).
    No fabrication of unrelated skills. Deduplicates (React vs React.js)."""
    if not jd_keywords:
        return _deduplicate_tools(skills_dict)

    corpus_parts = []
    for exp in (payload.experiences or [])[:5]:
        corpus_parts.append((exp.description or "") + " " + (exp.jobTitle or ""))
    for proj in (payload.projects or [])[:5]:
        corpus_parts.append((proj.description or "") + " " + (proj.techStack or ""))
    for ts in (payload.techSkills or [])[:20]:
        corpus_parts.append((ts.name or "").strip())
    corpus = " ".join(corpus_parts).lower()
    if not corpus.strip():
        return _deduplicate_tools(skills_dict)

    def category_for_kw(kw: str) -> str:
        """Map JD keyword to best-matching category. Prefer specific tech over tools."""
        k = kw.lower().strip()
        for cat, terms in SKILL_CATEGORIES.items():
            if any(t in k or k in t for t in terms):
                return cat
        return "tools"

    def user_has_skill_in_category(cat: str) -> bool:
        """Check if user has any skill in this category."""
        val = skills_dict.get(cat) or ""
        return bool(val and any(s.strip() for s in val.split(",")))

    added: dict[str, list[str]] = {
        "languages": [], "frontend": [], "backend": [], "genai": [], "tools": [], "devops": [],
    }
    for kw in jd_keywords:
        if not kw or len(kw) < 2:
            continue
        if _skill_already_in_skills(kw, skills_dict):
            continue
        cat = category_for_kw(kw)
        kw_in_corpus = kw.lower() in corpus
        kw_in_same_category = user_has_skill_in_category(cat) and cat != "tools"
        if not kw_in_corpus and not kw_in_same_category:
            continue
        if len(added[cat]) >= 8:
            continue
        # Allow more JD keywords in same category for 90%+ match target
        if not kw_in_corpus and kw_in_same_category and len(added[cat]) >= 6:
            continue
        display = kw.strip().title()
        if display in added[cat]:
            continue
        added[cat].append(display)

    out = dict(skills_dict)
    for cat in added:
        extras = added[cat]
        if not extras:
            continue
        existing_str = out.get(cat) or ""
        existing_list = [s.strip() for s in existing_str.split(",") if s.strip()]
        for x in extras:
            if _skill_already_in_skills(x, out):
                continue
            if x not in existing_list and len(existing_list) < 8:
                existing_list.append(x)
        if existing_list:
            out[cat] = ", ".join(existing_list[:8])

    return _deduplicate_tools(out)


def _deduplicate_tools(skills_dict: dict[str, str]) -> dict[str, str]:
    """Remove from Tools any skill that belongs in another category (e.g. React)."""
    tools_str = skills_dict.get("tools") or ""
    if not tools_str:
        return skills_dict
    others_combined = ""
    for cat in ("languages", "frontend", "backend", "genai", "devops"):
        others_combined += " " + (skills_dict.get(cat) or "")
    others_combined = others_combined.lower()
    tools_list = [s.strip() for s in tools_str.split(",") if s.strip()]
    filtered = []
    for t in tools_list:
        t_norm = _normalize_skill_for_dedup(t)
        if not t_norm:
            filtered.append(t)
            continue
        belongs_elsewhere = False
        for cat, terms in SKILL_CATEGORIES.items():
            if cat == "tools":
                continue
            if any(t_norm == _normalize_skill_for_dedup(term) for term in terms):
                belongs_elsewhere = True
                break
            if any(term in t.lower() or t.lower() in term for term in terms):
                belongs_elsewhere = True
                break
        if not belongs_elsewhere:
            filtered.append(t)
    result = dict(skills_dict)
    result["tools"] = ", ".join(filtered) if filtered else ""
    if not result["tools"]:
        result.pop("tools", None)
    return result


def _truncate_at_word(text: str, max_len: int = 200) -> str:
    """Truncate at word boundary; add '...' if truncated."""
    if not text or len(text) <= max_len:
        return text or ""
    cut = text[: max_len + 1]
    truncated = cut.rsplit(" ", 1)[0] if " " in cut else text[:max_len]
    return (truncated.rstrip() + "...") if len(text) > len(truncated) else truncated


def _parse_bullets(description: str, max_bullets: int = 4) -> list[str]:
    """Parse description into bullet points. Splits by newlines/dashes, or by sentences if single paragraph."""
    if not description:
        return []
    text = description.replace("•", "\n").replace("–", "\n").replace("- ", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) >= 2:
        return lines[:max_bullets]
    # Single long paragraph: split by sentence boundary for better bullet separation
    if lines and len(lines[0]) > 150:
        parts = re.split(r"\s*\.\s+", lines[0])
        result = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if not p.endswith(".") and not p.endswith("!"):
                p = p + "."
            result.append(p)
            if len(result) >= max_bullets:
                break
        if result:
            return result
    return lines[:max_bullets]


_MONTH_LONG = ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']
_MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _parse_date_to_parts(date_str: str) -> tuple:
    """Parse a date string into (month_1based, year) ints, or (None, None) on failure."""
    s = (date_str or '').strip()
    if not s:
        return None, None
    # "YYYY-MM"
    m = re.match(r'^(\d{4})-(\d{2})$', s)
    if m:
        return int(m.group(2)), int(m.group(1))
    # "Month YYYY" or "Mon YYYY"
    for i, (lng, sht) in enumerate(zip(_MONTH_LONG, _MONTH_SHORT), 1):
        m = re.match(rf'^({re.escape(lng)}|{re.escape(sht)})\s+(\d{{4}})$', s, re.I)
        if m:
            return i, int(m.group(2))
    return None, None


def _format_single_date(date_str: str, style: str) -> str:
    """Reformat a single date string into the requested display style."""
    s = (date_str or '').strip()
    if not s or s.lower() in ('present', 'current'):
        return s
    month, year = _parse_date_to_parts(s)
    if month is None:
        return s  # Can't parse — return as-is
    if style == 'Short (Jan YYYY)':
        return f"{_MONTH_SHORT[month - 1]} {year}"
    if style == 'Numeric (01/YYYY)':
        return f"{month:02d}/{year}"
    return f"{_MONTH_LONG[month - 1]} {year}"  # Long Name (January YYYY) — default


def _format_dates(start: str, end: str, style: str = 'Long Name (January YYYY)') -> str:
    """Format start/end into configured date style, or 'Mon YYYY - Present'."""
    if not start and not end:
        return ""
    fmt_start = _format_single_date(start or '', style)
    if not end or end.lower() in ("present", "current"):
        return f"{fmt_start} - Present" if fmt_start else "Present"
    return f"{fmt_start} - {_format_single_date(end, style)}"


def _identity(s: str) -> str:
    """Pass-through for HTML (Jinja2 autoescapes)."""
    return s or ""


def _bold_keywords_in_bullet(bullet: str, keywords: set[str]) -> str:
    """Wrap JD-relevant keywords in <strong> for emphasis. Returns HTML-safe string."""
    if not bullet or not keywords:
        return html.escape(bullet or "")
    escaped = html.escape(bullet)
    kw_list = sorted([k for k in keywords if k and len(k) >= 2], key=len, reverse=True)
    if not kw_list:
        return escaped
    pattern = "|".join(re.escape(k) for k in kw_list)
    return re.sub(f"({pattern})", r"<strong>\1</strong>", escaped, flags=re.I)


def _ats_friendly_name(first_name: str, last_name: str, job_title: str) -> str:
    """Build ATS-friendly resume name: FirstName_LastName_JobTitle (no special chars, underscores)."""
    first = (first_name or "").strip().replace(" ", "_")
    last = (last_name or "").strip().replace(" ", "_")
    title = (job_title or "Resume").strip().replace(" ", "_")[:40]
    parts = [p for p in [first, last, title] if p]
    if not parts:
        return "Resume"
    name = "_".join(parts)
    return re.sub(r"[^\w\-_]", "", name) or "Resume"


def _tailor_summary_llm(
    headline: str,
    summary: str,
    job_title: str,
    job_description: str,
    top_skills: list[str],
) -> str | None:
    """Use LLM to write a JD-tailored professional summary. Returns None on failure."""
    if not settings.openai_api_key or not job_description or len(job_description.strip()) < 80:
        return None
    if OpenAI is None:
        return None
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        jd_snippet = (job_description or "").strip()[:800]
        skills_str = ", ".join(top_skills[:8]) if top_skills else "N/A"
        prompt = f"""Write a 2-3 sentence professional resume summary (max 220 chars) for a candidate.
Use ONLY facts from the profile below. Do not invent. Start with the target role: {job_title or 'professional'}.
Weave in the most relevant skills from the candidate's list that match the job description.
Profile - Headline: {headline or 'N/A'}. Summary: {(summary or 'N/A')[:300]}
Skills: {skills_str}
Job description (excerpt): {jd_snippet[:500]}
Output ONLY the summary text, nothing else."""
        resp = client.chat.completions.create(
            model=getattr(settings, "openai_model", "gpt-4o-mini") or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150,
        )
        content = (resp.choices[0].message.content or "").strip()
        if content and len(content) > 50:
            return content[:220]
    except Exception as e:
        logger.warning("LLM summary tailoring failed: %s", e)
    return None


def _enhance_bullets_for_jd_llm(
    bullets: list[str],
    job_title: str,
    job_description: str,
    company: str,
    role: str,
    keywords: set[str],
) -> list[str] | None:
    """Use LLM to rewrite bullets to weave in JD keywords. Returns None on failure."""
    if not settings.openai_api_key or not bullets or not keywords or len((job_description or "").strip()) < 80:
        return None
    if OpenAI is None:
        return None
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        jd_snippet = (job_description or "").strip()[:600]
        kw_str = ", ".join(sorted(keywords)[:15])
        bullets_str = "\n".join(f"- {b}" for b in bullets[:4])
        prompt = f"""Rewrite these resume bullet points to better match the job description.
Rules: Use ONLY facts from the bullets. Do not invent. Weave in these JD keywords naturally where they fit: {kw_str}
Keep each bullet under 200 chars. Output exactly 4 bullets, one per line, starting with "- ".
Company: {company}. Role: {role}.
Original bullets:
{bullets_str}

Job description excerpt:
{jd_snippet[:400]}

Output ONLY the 4 rewritten bullets, one per line."""
        resp = client.chat.completions.create(
            model=getattr(settings, "openai_model", "gpt-4o-mini") or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            return None
        out = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                line = line[2:].strip()
            if line and len(line) > 20:
                out.append(line[:200])
        return out[:4] if len(out) >= 2 else None
    except Exception as e:
        logger.warning("LLM bullet enhancement failed: %s", e)
    return None


def _enhance_project_for_jd_llm(
    name: str,
    description: str,
    tech_stack: str,
    job_description: str,
    keywords: set[str],
) -> str | None:
    """Use LLM to rewrite project description to weave in JD keywords. Returns None on failure."""
    if not settings.openai_api_key or not description or not keywords or len((job_description or "").strip()) < 80:
        return None
    if OpenAI is None:
        return None
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        jd_snippet = (job_description or "").strip()[:500]
        kw_str = ", ".join(sorted(keywords)[:12])
        prompt = f"""Rewrite this project description to better match the job description.
Rules: Use ONLY facts from the original. Do not invent. Weave in these keywords naturally: {kw_str}
Keep under 220 chars. Output ONLY the rewritten description.
Project: {name}. Tech: {tech_stack or 'N/A'}.
Original: {description[:300]}

Job excerpt: {jd_snippet[:300]}

Output ONLY the rewritten description."""
        resp = client.chat.completions.create(
            model=getattr(settings, "openai_model", "gpt-4o-mini") or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150,
        )
        content = (resp.choices[0].message.content or "").strip()
        if content and len(content) > 30:
            return content[:220]
    except Exception as e:
        logger.warning("LLM project enhancement failed: %s", e)
    return None


def _build_professional_summary(
    payload,
    job_title: str,
    job_description: str,
    keywords: set[str],
    skills_dict: dict,
    escape_fn,
    skip_llm: bool = False,
) -> str:
    """
    Build professional summary from user profile.
    When skip_llm=True (live preview), use the user's text directly — no LLM calls.
    When skip_llm=False (initial generation), LLM tailors short/empty summaries.
    """
    headline = (payload.professionalHeadline or "").strip()
    summary = (payload.professionalSummary or "").strip()

    # Always prefer the user's own text — left panel must match right panel
    if summary and len(summary) >= 80:
        return escape_fn(_truncate_at_word(summary, max_len=1000))

    # For live preview: use whatever the user typed, even if short
    if skip_llm:
        return escape_fn(_truncate_at_word(summary or headline, max_len=1000)) if (summary or headline) else ""

    # LLM tailoring only during initial generation when summary is empty or very short
    all_skills: list[str] = []
    for val in (skills_dict or {}).values():
        if val:
            all_skills.extend(s.strip() for s in str(val).split(",") if s.strip())
    if keywords and all_skills:
        jd_skills = [s for s in all_skills if any(k in s.lower() for k in keywords)]
        other_skills = [s for s in all_skills if s not in jd_skills]
        all_skills = (jd_skills or all_skills)[:6] + (other_skills or [])[:4]
    top_skills = all_skills[:8] if all_skills else []

    if job_title or (job_description and len((job_description or "").strip()) >= 80):
        tailored = _tailor_summary_llm(headline, summary, job_title or "", job_description or "", top_skills)
        if tailored:
            return escape_fn(tailored[:220])
    return ""


def build_resume_context_from_payload(
    payload: ProfilePayload,
    job_title: str,
    job_description: str,
    for_html: bool = False,
    raw_awards: list | None = None,
    skip_llm: bool = False,
    date_format_style: str = 'Long Name (January YYYY)',
) -> dict:
    """Build Jinja2 context directly from a ProfilePayload (no DB access needed).
    skip_llm=True: skip all LLM enhancement calls — use for live preview (~50ms response).
    skip_llm=False: run LLM bullet/project/summary enhancement — use for initial generation."""
    escape_fn = _identity if for_html else _latex_escape
    keywords = _get_jd_keywords(job_description or "")

    name = f"{payload.firstName or ''} {payload.lastName or ''}".strip() or "Your Name"
    links = payload.links or {}

    def _ensure_url(url: str) -> str:
        if not url:
            return ""
        u = (url or "").strip()
        if u and not u.startswith(("http://", "https://")):
            return f"https://{u}"
        return u

    # Skills
    skills = _categorize_skills(payload.techSkills or [])
    if not any(skills.values()) and payload.techSkills:
        skills["languages"] = ", ".join((s.name or "").strip() for s in payload.techSkills[:10])
    skills = _enrich_skills_with_jd_keywords(skills, payload, keywords)

    # Experiences: max 3 roles, 4 bullets each
    experiences: list[dict] = []
    for exp in (payload.experiences or [])[:3]:
        bullets = _parse_bullets(exp.description or "", max_bullets=4)
        if keywords and bullets:
            # Only re-sort by keyword score during initial AI generation (skip_llm=False).
            # When skip_llm=True (preview/download), preserve the order the user sees in the editor.
            if not skip_llm:
                bullets = sorted(bullets, key=lambda b: -_score_bullet(b, keywords))[:4]
            else:
                bullets = bullets[:4]
            if not skip_llm:
                total_score = sum(_score_bullet(b, keywords) for b in bullets)
                if total_score < len(keywords) * 0.3 and len(keywords) >= 3:
                    enhanced = _enhance_bullets_for_jd_llm(
                        bullets, job_title or "", job_description or "",
                        exp.companyName or "Company", exp.jobTitle or "Role", keywords,
                    )
                    if enhanced:
                        bullets = enhanced
        elif bullets:
            bullets = bullets[:4]
        bullet_texts = [_truncate_at_word(b or "", max_len=350) for b in bullets]
        if for_html and keywords:
            bullets_out = [_bold_keywords_in_bullet(t, keywords) for t in bullet_texts]
        else:
            bullets_out = [escape_fn(t) for t in bullet_texts]
        experiences.append({
            "company": escape_fn(exp.companyName or "Company"),
            "location": escape_fn(exp.location or ""),
            "dates": escape_fn(_format_dates(exp.startDate or "", exp.endDate or "", style=date_format_style)),
            "title": escape_fn(exp.jobTitle or "Role"),
            "bullets": bullets_out,
        })

    # Education: max 2
    educations: list[dict] = []
    for edu in (payload.educations or [])[:2]:
        degree = edu.degree or ""
        if edu.fieldOfStudy:
            degree = f"{degree} in {edu.fieldOfStudy}" if degree else edu.fieldOfStudy
        educations.append({
            "institution": escape_fn(edu.institution or "Institution"),
            "location": escape_fn(edu.location or ""),
            "dates": escape_fn(_format_dates(edu.startYear or "", edu.endYear or "", style=date_format_style)),
            "degree": escape_fn(degree),
            "grade": escape_fn(edu.grade or ""),
        })

    # Projects: max 2
    projects: list[dict] = []
    for proj in (payload.projects or [])[:2]:
        desc = proj.description or ""
        if not skip_llm and keywords and desc and _score_bullet(desc, keywords) < len(keywords) * 0.2 and len(keywords) >= 3:
            enhanced = _enhance_project_for_jd_llm(
                proj.name or "Project", desc, proj.techStack or "",
                job_description or "", keywords,
            )
            if enhanced:
                desc = enhanced
        # No truncation for project descriptions — show the full text the user wrote
        desc = _truncate_at_word(desc, max_len=1000)
        projects.append({
            "name": escape_fn(proj.name or "Project"),
            "techStack": escape_fn((proj.techStack or "").strip()),
            "description": escape_fn(desc or ""),
        })

    # Professional summary
    professional_summary = _build_professional_summary(
        payload=payload,
        job_title=job_title or "",
        job_description=job_description or "",
        keywords=keywords,
        skills_dict=skills,
        escape_fn=escape_fn,
        skip_llm=skip_llm,
    )

    # Awards
    aw = raw_awards if raw_awards is not None else []
    if isinstance(aw, list):
        awards = [escape_fn(str(a)) for a in aw if a][:2]
    elif isinstance(aw, str):
        awards = [escape_fn(aw)]
    else:
        awards = []

    return {
        "name": escape_fn(name),
        "professional_summary": professional_summary,
        "email": escape_fn(payload.email or ""),
        "phone": escape_fn(payload.phone or ""),
        "linkedin": _ensure_url(getattr(links, "linkedInUrl", "") if hasattr(links, "linkedInUrl") else (links.get("linkedInUrl", "") if isinstance(links, dict) else "")),
        "github": _ensure_url(getattr(links, "githubUrl", "") if hasattr(links, "githubUrl") else (links.get("githubUrl", "") if isinstance(links, dict) else "")),
        "portfolio": _ensure_url(getattr(links, "portfolioUrl", "") if hasattr(links, "portfolioUrl") else (links.get("portfolioUrl", "") if isinstance(links, dict) else "")),
        "skills": skills,
        "experiences": experiences,
        "educations": educations,
        "projects": projects,
        "awards": awards,
    }


def build_resume_context(
    profile: Profile,
    job_title: str,
    job_description: str,
    for_html: bool = False,
) -> dict:
    """Build Jinja2 context from Profile ORM model. Delegates to build_resume_context_from_payload."""
    payload = profile_model_to_payload(profile)
    prefs = profile.preferences or {}
    raw_aw = prefs.get("awards", prefs.get("certificates", []))
    if isinstance(raw_aw, str):
        raw_aw = [raw_aw]
    elif not isinstance(raw_aw, list):
        raw_aw = []
    return build_resume_context_from_payload(payload, job_title, job_description, for_html, raw_aw)


def build_resume_text_from_context(context: dict) -> str:
    """Build plain text from resume context for editable content. Matches rendered output."""
    parts = [f"{context.get('name', '')}"]
    if context.get("professional_summary"):
        parts.append(f"Professional Summary: {context['professional_summary']}")
    contact = []
    if context.get("email"):
        contact.append(context["email"])
    if context.get("phone"):
        contact.append(context["phone"])
    if contact:
        parts.append(" | ".join(contact))
    if context.get("skills"):
        for label, val in context["skills"].items():
            if val:
                parts.append(f"{label.title()}: {val}")
    for exp in context.get("experiences", []) or []:
        parts.append(f"\n{exp.get('company', '')} | {exp.get('dates', '')}")
        parts.append(exp.get("title", ""))
        for b in exp.get("bullets", []) or []:
            text = re.sub(r"<[^>]+>", "", str(b or ""))
            parts.append(f"  • {text}")
    for edu in context.get("educations", []) or []:
        parts.append(f"\n{edu.get('institution', '')} | {edu.get('degree', '')}")
        parts.append(edu.get("dates", ""))
    for proj in context.get("projects", []) or []:
        name = proj.get("name", "")
        tech = proj.get("techStack", "")
        desc = proj.get("description", "")
        if tech:
            parts.append(f"\n{name} ({tech}): {desc}")
        else:
            parts.append(f"\n{name}: {desc}")
    for award in context.get("awards", []) or []:
        parts.append(f"  • {award}")
    return "\n".join(parts).strip() or "Resume content"


TEMPLATE_MAP = {
    "classic": "resume.html",
    "accent": "resume_accent.html",
    "minimalist": "resume_minimalist.html",
    "modern": "resume_modern.html",
    "executive": "resume_executive.html",
    "harvard": "resume_harvard.html",
    "elegant": "resume_elegant.html",
    "impact": "resume_impact.html",
}


def _normalize_font_params(font_family: str | None, font_size: str | None, line_height: str | None) -> tuple[str, str, str]:
    """Normalize font params for templates. Returns (font_family, font_size, line_height)."""
    families = ("Times New Roman", "Arial", "Georgia", "Calibri", "Garamond", "Helvetica", "Verdana", "Lato", "Segoe UI")
    sizes_map = {"9pt": "9pt", "9px": "9pt", "10pt": "10pt", "10px": "10pt", "10.5pt": "10.5pt", "10.5px": "10.5pt", "11pt": "11pt", "11px": "11pt", "12pt": "12pt", "12px": "12pt", "12.5pt": "12pt"}
    heights = ("1.0", "1.1", "1.2", "1.25", "1.3", "1.5")
    ff = (font_family or "").strip() or "Times New Roman"
    if ff not in families:
        ff = "Times New Roman"
    fs_raw = (font_size or "").strip()
    fs = sizes_map.get(fs_raw) or (fs_raw.replace("px", "pt") if fs_raw else "11pt")
    if fs not in ("9pt", "10pt", "10.5pt", "11pt", "12pt"):
        fs = "11pt"
    lh = (line_height or "").strip() or "1.25"
    if lh not in heights:
        lh = "1.25"
    return (ff, fs, lh)


def render_html_resume(context: dict, template_dir: Path | None = None, template_id: str = "classic") -> str:
    """Render HTML resume from Jinja2 template with context. Returns HTML string."""
    if template_dir is None:
        template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template_name = TEMPLATE_MAP.get((template_id or "classic").lower(), "resume.html")
    try:
        template = env.get_template(template_name)
    except Exception:
        template = env.get_template("resume.html")
    return template.render(**context)


def html_to_pdf_weasyprint(html_content: str, work_dir: Path) -> bytes:
    """Convert HTML to PDF using WeasyPrint. Returns PDF bytes."""
    try:
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
    except ImportError as err:
        raise RuntimeError(
            "WeasyPrint not installed. Run: pip install weasyprint"
        ) from err

    html_path = work_dir / "resume.html"
    html_path.write_text(html_content, encoding="utf-8")
    pdf_path = work_dir / "resume.pdf"
    font_config = FontConfiguration()
    doc = HTML(filename=str(html_path))
    doc.write_pdf(pdf_path, font_config=font_config)
    if not pdf_path.exists():
        raise RuntimeError("WeasyPrint did not produce PDF")
    return pdf_path.read_bytes()


_PREVIEW_CACHE: OrderedDict[str, tuple[bytes, float]] = OrderedDict()
_PREVIEW_CACHE_LOCK = threading.Lock()
_PREVIEW_CACHE_TTL = 90
_PREVIEW_CACHE_MAX = 32


def _preview_cache_key(user_id: int, template_id: str, ff: str, fs: str, lh: str, job_title: str, job_description: str) -> str:
    h = hashlib.sha256(f"{job_title}|{job_description}".encode()).hexdigest()[:16]
    return f"preview:{user_id}:{template_id}:{ff}:{fs}:{lh}:{h}"


def clear_preview_cache_for_user(user_id: int) -> None:
    """Clear in-memory preview cache for a user so next preview uses fresh profile."""
    with _PREVIEW_CACHE_LOCK:
        to_del = [k for k in _PREVIEW_CACHE if k.startswith(f"preview:{user_id}:")]
        for k in to_del:
            del _PREVIEW_CACHE[k]
        if to_del:
            logger.debug("Resume preview cache cleared for user_id=%s entries=%d", user_id, len(to_del))


def generate_resume_preview_pdf(
    db: Session,
    user: User,
    job_title: str,
    job_description: str,
    template_id: str = "classic",
    font_family: str | None = None,
    font_size: str | None = None,
    line_height: str | None = None,
    profile_override: dict | None = None,
    design_config: dict | None = None,
) -> bytes:
    """
    Generate resume PDF without saving. Returns PDF bytes.
    When profile_override is provided (current editor state), uses it directly so the
    downloaded PDF matches the live preview exactly. Cache is bypassed for overrides.
    design_config: full design settings applied to both HTML and WeasyPrint rendering.
    """
    ff, fs, lh = _normalize_font_params(font_family, font_size, line_height)
    dcfg = design_config or {}

    # Cache only applies when using the DB profile (not a live editor override)
    if not profile_override and not dcfg:
        cache_key = _preview_cache_key(user.id, template_id, ff, fs, lh, job_title or "", job_description or "")
        with _PREVIEW_CACHE_LOCK:
            if cache_key in _PREVIEW_CACHE:
                pdf_bytes, expiry = _PREVIEW_CACHE[cache_key]
                if time.time() < expiry:
                    _PREVIEW_CACHE.move_to_end(cache_key)
                    logger.debug("Resume preview cache hit template=%s", template_id)
                    return pdf_bytes
                del _PREVIEW_CACHE[cache_key]

    date_fmt = dcfg.get('format_dates', 'Long Name (January YYYY)')

    if profile_override:
        try:
            payload = ProfilePayload(**profile_override)
        except Exception:
            payload = ProfilePayload()
        context = build_resume_context_from_payload(
            payload, job_title or "", job_description or "",
            for_html=True, date_format_style=date_fmt,
        )
    else:
        profile = ProfileService.get_or_create_profile(db, user)
        context = build_resume_context(profile, job_title or "", job_description or "", for_html=True)

    _apply_design_config_to_context(context, dcfg)

    context["font_family"] = ff
    context["font_size"] = fs
    context["line_height"] = lh
    template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
    html_content = render_html_resume(context, template_dir, template_id=template_id)

    # Inject design-config CSS overrides (WeasyPrint uses @page rules; ignores @media screen).
    if dcfg:
        design_css = _build_design_css_overrides(dcfg, template_id or 'classic')
        if design_css:
            html_content = html_content.replace("</head>", design_css + "</head>")
        sections_order = dcfg.get('sections_order') or []
        if sections_order:
            html_content = _reorder_sections_html(html_content, sections_order, template_id or 'classic')

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        pdf_bytes = html_to_pdf_weasyprint(html_content, work_dir)

    if not profile_override and not dcfg:
        with _PREVIEW_CACHE_LOCK:
            while len(_PREVIEW_CACHE) >= _PREVIEW_CACHE_MAX and _PREVIEW_CACHE:
                _PREVIEW_CACHE.popitem(last=False)
            _PREVIEW_CACHE[cache_key] = (pdf_bytes, time.time() + _PREVIEW_CACHE_TTL)
            _PREVIEW_CACHE.move_to_end(cache_key)

    return pdf_bytes


# ── Design-config helpers ────────────────────────────────────────────────────

_SECTION_CTX_MAP = {
    'summary': 'professional_summary',
    'experience': 'experiences',
    'skills': 'skills',
    'education': 'educations',
    'projects': 'projects',
    'certifications': 'awards',
}

_SECTION_TITLE_PATTERNS = {
    'summary': re.compile(r'summary', re.I),
    'experience': re.compile(r'experience', re.I),
    'skills': re.compile(r'skills', re.I),
    'education': re.compile(r'education', re.I),
    'projects': re.compile(r'projects', re.I),
    'certifications': re.compile(r'awards|certif', re.I),
}


def _apply_design_config_to_context(context: dict, design_config: dict) -> dict:
    """Hide sections not in sections_visible by clearing their context keys."""
    sections_visible = (design_config or {}).get('sections_visible') or []
    if not sections_visible:
        return context  # Empty list = all sections visible
    for key, ctx_key in _SECTION_CTX_MAP.items():
        if key not in sections_visible:
            val = context.get(ctx_key)
            if isinstance(val, list):
                context[ctx_key] = []
            elif isinstance(val, dict):
                context[ctx_key] = {}
            elif isinstance(val, str):
                context[ctx_key] = ''
    return context


def _reorder_sections_html(html: str, sections_order: list, template_id: str) -> str:
    """Post-process rendered HTML to reorder section blocks per sections_order.
    Skips two-column templates (modern, impact) where safe reordering is not possible."""
    if not sections_order or (template_id or '').lower() in ('modern', 'impact'):
        return html
    body_m = re.search(r'(<body[^>]*>)(.*)(</body>)', html, re.DOTALL)
    if not body_m:
        return html
    head_chunk = html[:body_m.start(2)]
    body_content = body_m.group(2)
    tail_chunk = html[body_m.end(2):]

    # Split at each <div class="section"> boundary; parts[0] = header area
    parts = re.split(r'(?=<div\s+class="section")', body_content)
    if len(parts) <= 1:
        return html
    header_block = parts[0]
    section_blocks = parts[1:]

    def _identify_block(block: str) -> str:
        snippet = block[:300]
        for key, pattern in _SECTION_TITLE_PATTERNS.items():
            if pattern.search(snippet):
                return key
        return 'unknown'

    mapped: dict[str, str] = {}
    unknowns: list[str] = []
    for block in section_blocks:
        key = _identify_block(block)
        if key == 'unknown':
            unknowns.append(block)
        else:
            mapped[key] = block

    ordered = [mapped[k] for k in sections_order if k in mapped]
    # Append any sections that exist in HTML but weren't in sections_order
    ordered += [mapped[k] for k in mapped if k not in sections_order] + unknowns
    return head_chunk + header_block + ''.join(ordered) + tail_chunk


def _build_design_css_overrides(design_config: dict, template_id: str) -> str:
    """Generate a <style> block with CSS overrides for all active design-config settings."""
    if not design_config:
        return ''
    lines: list[str] = []
    tid = (template_id or 'classic').lower()

    # ── Color scheme ─────────────────────────────────────────────────────────
    color_scheme_id = design_config.get('color_scheme_id', '')
    if color_scheme_id:
        from backend.app.services.templates.registry import get_template as _get_tmpl
        tmpl_meta = _get_tmpl(tid)
        if tmpl_meta:
            schemes = tmpl_meta.get('color_schemes', [])
            scheme = next((s for s in schemes if s['id'] == color_scheme_id), None)
            if not scheme and schemes:
                scheme = schemes[0]  # fallback to template default
            if scheme:
                p = scheme['primary']
                bg = scheme.get('bg', '#ffffff')
                lines += [
                    f".section-title {{ color: {p} !important; border-color: {p} !important; }}",
                    f".header-band {{ background-color: {p} !important; }}",
                    f"td.sidebar {{ background-color: {p} !important; }}",
                ]
                if bg != '#ffffff':
                    lines.append(f"body {{ background-color: {bg}; }}")

    # ── Margin size ──────────────────────────────────────────────────────────
    margin_map = {'Small': '0.3in', 'Medium': '0.5in', 'Large': '0.75in'}
    margin = margin_map.get(design_config.get('margin_size', 'Medium'), '0.5in')
    lines += [
        f"@page {{ margin: {margin} !important; }}",
        f"@media screen {{ body {{ padding: {margin} !important; box-sizing: border-box; }} }}",
        f"@media screen {{ .header-band {{ margin-left: -{margin} !important; "
        f"margin-right: -{margin} !important; margin-top: -{margin} !important; }} }}",
    ]

    # ── Header alignment ─────────────────────────────────────────────────────
    align_val = 'center' if design_config.get('header_align', 'Center') == 'Center' else 'left'
    lines += [
        f".header {{ text-align: {align_val} !important; }}",
        f".header-band {{ text-align: {align_val} !important; }}",
    ]

    # ── Section spacing ──────────────────────────────────────────────────────
    spacing_map = {'compact': '6px', 'normal': '12px', 'spacious': '20px'}
    spacing = spacing_map.get(design_config.get('section_spacing', 'normal'), '12px')
    lines += [
        f".section {{ margin-top: {spacing} !important; }}",
        f".main .section {{ margin-top: {spacing} !important; }}",
    ]

    # ── Section separator line ────────────────────────────────────────────────
    if not design_config.get('section_separator', True):
        lines.append(".section-title { border-bottom: none !important; }")

    # ── Bullet icon ──────────────────────────────────────────────────────────
    bullet_map = {'• Bullet': '•', '– Dash': '–', '▸ Arrow': '▸'}
    bullet_char = bullet_map.get(design_config.get('bullet_icon', '• Bullet'), '•')
    lines += [
        "ul { list-style: none !important; padding-left: 1.2em !important; }",
        f"li::before {{ content: '{bullet_char} '; }}",
    ]

    # ── Name uppercase ───────────────────────────────────────────────────────
    if design_config.get('name_capitalize', False):
        lines.append(".name { text-transform: uppercase !important; }")

    # ── Page size ────────────────────────────────────────────────────────────
    if design_config.get('page_size') == 'A4':
        lines.append("@page { size: A4 !important; }")

    return "<style>\n/* design-config overrides */\n" + "\n".join(lines) + "\n</style>\n"


def generate_resume_preview_html(
    db: Session,
    user: User,
    job_title: str,
    job_description: str,
    template_id: str = "classic",
    font_family: str | None = None,
    font_size: str | None = None,
    line_height: str | None = None,
    profile_override: dict | None = None,
    design_config: dict | None = None,
) -> str:
    """
    Return rendered Jinja2 HTML string using the SAME templates as PDF generation.
    This guarantees pixel-perfect WYSIWYG: preview == download.
    Fast (~50ms) — no WeasyPrint conversion needed.
    profile_override: current editor profile state passed directly from the frontend,
    bypassing the DB so live edits appear instantly without waiting for the 700ms save debounce.
    design_config: full design settings (color scheme, margins, spacing, sections, etc.).
    """
    dcfg = design_config or {}
    date_fmt = dcfg.get('format_dates', 'Long Name (January YYYY)')

    if profile_override:
        try:
            payload = ProfilePayload(**profile_override)
        except Exception:
            payload = ProfilePayload()
        # skip_llm=True: preview must be fast (~50ms). LLM enhancement already ran at generation time.
        context = build_resume_context_from_payload(
            payload, job_title or "", job_description or "",
            for_html=True, skip_llm=True, date_format_style=date_fmt,
        )
    else:
        profile = ProfileService.get_or_create_profile(db, user)
        # Even without override, skip LLM for preview — this endpoint is for display only.
        context = build_resume_context_from_payload(
            profile_model_to_payload(profile), job_title or "", job_description or "",
            for_html=True, skip_llm=True, date_format_style=date_fmt,
        )

    _apply_design_config_to_context(context, dcfg)

    ff, fs, lh = _normalize_font_params(font_family, font_size, line_height)
    context["font_family"] = ff
    context["font_size"] = fs
    context["line_height"] = lh

    template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
    html = render_html_resume(context, template_dir, template_id=template_id)

    # Inject baseline screen CSS for templates that don't define their own @media screen rules.
    # WeasyPrint ignores @media screen entirely, so this never affects the PDF output.
    # Templates that already include @media screen (modern, executive, harvard, elegant, impact) are skipped.
    _templates_with_own_screen_css = {"modern", "executive", "harvard", "elegant", "impact"}
    if (template_id or "classic").lower() not in _templates_with_own_screen_css:
        screen_css = """<style>
@media screen {
  body { padding: 0.5in !important; box-sizing: border-box; }
  .header-band { margin-left: -0.5in !important; margin-right: -0.5in !important; margin-top: -0.5in !important; }
}
</style>"""
        html = html.replace("</head>", screen_css + "\n</head>")

    # Design-config CSS overrides injected last — takes precedence over template defaults.
    if dcfg:
        design_css = _build_design_css_overrides(dcfg, template_id or 'classic')
        if design_css:
            html = html.replace("</head>", design_css + "</head>")
        sections_order = dcfg.get('sections_order') or []
        if sections_order:
            html = _reorder_sections_html(html, sections_order, template_id or 'classic')

    return html


def generate_resume_html(
    db: Session,
    user: User,
    job_title: str,
    job_description: str,
    template_id: str = "classic",
    font_family: str | None = None,
    font_size: str | None = None,
    line_height: str | None = None,
) -> dict:
    """
    Generate resume using Jinja2 HTML template + WeasyPrint.
    Same user profile with JD optimizations (prioritized bullets by keywords).
    Returns: { resume_id, resume_url, presigned_url, resume_name, resume_text }
    """
    profile = ProfileService.get_or_create_profile(db, user)
    context = build_resume_context(profile, job_title or "", job_description or "", for_html=True)
    ff, fs, lh = _normalize_font_params(font_family, font_size, line_height)
    context["font_family"] = ff
    context["font_size"] = fs
    context["line_height"] = lh

    template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
    html_content = render_html_resume(context, template_dir, template_id=template_id)

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        pdf_bytes = html_to_pdf_weasyprint(html_content, work_dir)

    payload = profile_model_to_payload(profile)
    ats_name = _ats_friendly_name(payload.firstName or "", payload.lastName or "", job_title or "Resume")
    filename = f"{ats_name}_{uuid.uuid4().hex[:8]}.pdf"
    if not filename.endswith(".pdf"):
        filename += ".pdf"

    if settings.aws_access_key_id and settings.aws_secret_access_key:
        result = upload_file_to_s3(
            file_buffer=pdf_bytes,
            file_name=filename,
            user_id=user.id,
            mime_type="application/pdf",
            key_prefix="user-profiles",
        )
        resume_url = result["url"]
        key = result["key"]
        presigned_url = generate_presigned_url(key)
    else:
        upload_path = Path(settings.upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)
        file_path = upload_path / filename
        file_path.write_bytes(pdf_bytes)
        resume_url = f"/{settings.upload_dir}/{filename}"
        presigned_url = resume_url

    resume_name = ats_name
    resume_text = build_resume_text_from_context(context)

    # Build serializable profile snapshot for per-JD storage
    try:
        profile_snapshot = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    except Exception:
        profile_snapshot = None

    for r in db.query(UserResume).filter(UserResume.user_id == user.id).all():
        r.is_default = 0
    ur = UserResume(
        user_id=user.id,
        resume_url=resume_url,
        resume_name=resume_name,
        resume_text=resume_text,
        is_default=1,
        resume_profile_snapshot=profile_snapshot,
        job_title=(job_title or "").strip()[:255] or None,
        job_description_snippet=(job_description or "").strip()[:1000] or None,
    )
    db.add(ur)
    db.commit()
    db.refresh(ur)

    logger.info(
        "Resume generated (HTML/WeasyPrint) user_id=%s resume_id=%s job_title=%s",
        user.id,
        ur.id,
        job_title,
    )

    return {
        "resume_id": ur.id,
        "resume_url": resume_url,
        "presigned_url": presigned_url,
        "resume_name": ur.resume_name,
        "resume_text": resume_text,
    }


def render_latex(template_content: str, context: dict) -> str:
    """Render Jinja2 template with context. Returns LaTeX source string."""
    env = Environment(loader=BaseLoader(), autoescape=False)
    template = env.from_string(template_content)
    return template.render(**context)


def compile_latex_to_pdf(latex_source: str, work_dir: Path) -> bytes:
    """Compile LaTeX source to PDF using pdflatex. Returns PDF bytes."""
    tex_path = work_dir / "resume.tex"
    tex_path.write_text(latex_source, encoding="utf-8")

    glyph_path = work_dir / "glyphtounicode.tex"
    if not glyph_path.exists():
        glyph_path.write_text("% stub - required by hyperref\n\\ProvidesFile{glyphtounicode.tex}\n", encoding="utf-8")

    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(work_dir), str(tex_path)],
            capture_output=True,
            timeout=60,
            check=True,
            cwd=str(work_dir),
        )
    except subprocess.CalledProcessError as e:
        stdout = (e.stdout or b"").decode(errors="replace")
        stderr = (e.stderr or b"").decode(errors="replace")
        combined = " ".join(s.strip() for s in (stdout, stderr) if s.strip())
        logger.error("pdflatex failed: %s", combined)
        raise RuntimeError(f"LaTeX compilation failed: {combined or 'Unknown error'}") from e
    except FileNotFoundError:
        raise RuntimeError(
            "pdflatex not found. Install LaTeX: macOS: brew install --cask mactex | Linux: apt install texlive-latex-base | Windows: MiKTeX"
        )

    pdf_path = work_dir / "resume.pdf"
    if not pdf_path.exists():
        raise RuntimeError("PDF was not produced by pdflatex")
    return pdf_path.read_bytes()


def generate_resume(
    db: Session,
    user: User,
    job_title: str,
    job_description: str,
    template_id: int | None = None,
) -> dict:
    """
    Generate a tailored resume for the user based on job title and description.
    Fetches template from DB, builds context, compiles PDF, uploads to S3, saves to user_resumes.

    Returns:
        { "resume_id", "resume_url", "presigned_url", "resume_name" }
    """
    if ResumeTemplate is None:
        raise ValueError("ResumeTemplate model not available. Use POST /resume/generate for HTML/WeasyPrint flow.")
    profile = ProfileService.get_or_create_profile(db, user)
    template = (
        db.query(ResumeTemplate).filter(ResumeTemplate.id == template_id).first()
        if template_id
        else db.query(ResumeTemplate).filter(ResumeTemplate.is_default == 1).first()
    )
    if not template:
        raise ValueError("No resume template found. Run migration 003 to seed default template.")

    context = build_resume_context(profile, job_title or "", job_description or "")
    latex_source = render_latex(template.latex_content, context)

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        pdf_bytes = compile_latex_to_pdf(latex_source, work_dir)

    filename = f"resume_{job_title.replace(' ', '_')[:30]}_{uuid.uuid4().hex[:8]}.pdf"
    if not filename.endswith(".pdf"):
        filename += ".pdf"

    if settings.aws_access_key_id and settings.aws_secret_access_key:
        result = upload_file_to_s3(
            file_buffer=pdf_bytes,
            file_name=filename,
            user_id=user.id,
            mime_type="application/pdf",
            key_prefix="user-profiles",
        )
        resume_url = result["url"]
        key = result["key"]
        presigned_url = generate_presigned_url(key)
    else:
        upload_path = Path(settings.upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)
        file_path = upload_path / filename
        file_path.write_bytes(pdf_bytes)
        resume_url = f"/{settings.upload_dir}/{filename}"
        presigned_url = resume_url

    resume_name = f"{job_title or 'Resume'} (generated)"
    _payload2 = profile_model_to_payload(profile)
    resume_text = build_resume_text_from_payload(_payload2)

    try:
        profile_snapshot2 = _payload2.model_dump() if hasattr(_payload2, "model_dump") else _payload2.dict()
    except Exception:
        profile_snapshot2 = None

    # Mark other resumes as non-default
    for r in db.query(UserResume).filter(UserResume.user_id == user.id).all():
        r.is_default = 0
    ur = UserResume(
        user_id=user.id,
        resume_url=resume_url,
        resume_name=resume_name,
        resume_text=resume_text,
        is_default=1,
        resume_profile_snapshot=profile_snapshot2,
        job_title=(job_title or "").strip()[:255] or None,
        job_description_snippet=(job_description or "").strip()[:1000] or None,
    )
    db.add(ur)
    db.commit()
    db.refresh(ur)

    logger.info(
        "Resume generated user_id=%s resume_id=%s job_title=%s",
        user.id,
        ur.id,
        job_title,
    )

    return {
        "resume_id": ur.id,
        "resume_url": resume_url,
        "presigned_url": presigned_url,
        "resume_name": ur.resume_name,
    }


def generate_resume_preview(
    db: Session,
    user: User,
    job_title: str,
    job_description: str,
    template_id: int | None = None,
) -> dict:
    """
    Generate a resume preview (PDF) without saving to user_resumes.
    Returns presigned_url for viewing. File stored under user-profiles/{user_id}/preview_*.pdf
    """
    if ResumeTemplate is None:
        raise ValueError("ResumeTemplate model not available. Use POST /resume/generate for HTML/WeasyPrint flow.")
    profile = ProfileService.get_or_create_profile(db, user)
    template = (
        db.query(ResumeTemplate).filter(ResumeTemplate.id == template_id).first()
        if template_id
        else db.query(ResumeTemplate).filter(ResumeTemplate.is_default == 1).first()
    )
    if not template:
        raise ValueError("No resume template found.")

    context = build_resume_context(profile, job_title or "", job_description or "")
    latex_source = render_latex(template.latex_content, context)

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        pdf_bytes = compile_latex_to_pdf(latex_source, work_dir)

    filename = f"preview_{uuid.uuid4().hex[:8]}.pdf"

    if settings.aws_access_key_id and settings.aws_secret_access_key:
        result = upload_file_to_s3(
            file_buffer=pdf_bytes,
            file_name=filename,
            user_id=user.id,
            mime_type="application/pdf",
            key_prefix="user-profiles",
        )
        presigned_url = generate_presigned_url(result["key"])
    else:
        upload_path = Path(settings.upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)
        file_path = upload_path / filename
        file_path.write_bytes(pdf_bytes)
        presigned_url = f"/{settings.upload_dir}/{filename}"

    return {"presigned_url": presigned_url, "template_name": template.name}
