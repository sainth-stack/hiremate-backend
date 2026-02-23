"""
Dynamic resume generation: fetch profile, match JD keywords.
Uses Jinja2 for HTML templates and WeasyPrint for HTML→PDF conversion.
Same user profile with JD optimizations (prioritized bullets by keywords).
"""
import html
import re
import subprocess
import tempfile
import uuid
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
    """Add JD keywords to skills when they appear in profile (experiences, projects).
    No fabrication. Deduplicates (React vs React.js). Ensures correct category placement."""
    if not jd_keywords:
        return _deduplicate_tools(skills_dict)

    corpus_parts = []
    for exp in (payload.experiences or [])[:5]:
        corpus_parts.append((exp.description or "") + " " + (exp.jobTitle or ""))
    for proj in (payload.projects or [])[:5]:
        corpus_parts.append((proj.description or "") + " " + (proj.techStack or ""))
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

    added: dict[str, list[str]] = {
        "languages": [], "frontend": [], "backend": [], "genai": [], "tools": [], "devops": [],
    }
    for kw in jd_keywords:
        if not kw or len(kw) < 2:
            continue
        if _skill_already_in_skills(kw, skills_dict):
            continue
        if kw.lower() not in corpus:
            continue
        cat = category_for_kw(kw)
        display = kw.strip().title()
        lst = added[cat]
        if display in lst or len(lst) >= 8:
            continue
        lst.append(display)

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


def _format_dates(start: str, end: str) -> str:
    """Format start/end into 'Mon YYYY - Mon YYYY' or 'Mon YYYY - Present'."""
    if not start and not end:
        return ""
    if not end or end.lower() in ("present", "current"):
        return f"{start or ''} - Present"
    return f"{start or ''} - {end}"


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


def _build_professional_summary(
    payload,
    job_title: str,
    job_description: str,
    keywords: set[str],
    skills_dict: dict,
    escape_fn,
) -> str:
    """
    Build professional summary from user profile + JD using LLM.
    JD and OpenAI required; no fallback.
    """
    headline = (payload.professionalHeadline or "").strip()
    summary = (payload.professionalSummary or "").strip()

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


def build_resume_context(
    profile: Profile,
    job_title: str,
    job_description: str,
    for_html: bool = False,
) -> dict:
    """Build Jinja2 context from profile, job title, and JD. Prioritizes bullets by JD relevance.
    Uses same user profile - only reorders/prioritizes content by JD keywords (no fabrication)."""
    escape_fn = _identity if for_html else _latex_escape
    payload = profile_model_to_payload(profile)
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

    # Experiences: max 3 roles, 4 bullets each (single-page, fuller content)
    experiences: list[dict] = []
    for exp in (payload.experiences or [])[:3]:
        bullets = _parse_bullets(exp.description or "", max_bullets=4)
        if keywords and bullets:
            bullets = sorted(bullets, key=lambda b: -_score_bullet(b, keywords))[:4]
        elif bullets:
            bullets = bullets[:4]
        bullet_texts = [_truncate_at_word(b or "", max_len=200) for b in bullets]
        if for_html and keywords:
            bullets_out = [_bold_keywords_in_bullet(t, keywords) for t in bullet_texts]
        else:
            bullets_out = [escape_fn(t) for t in bullet_texts]
        experiences.append({
            "company": escape_fn(exp.companyName or "Company"),
            "location": escape_fn(exp.location or ""),
            "dates": escape_fn(_format_dates(exp.startDate or "", exp.endDate or "")),
            "title": escape_fn(exp.jobTitle or "Role"),
            "bullets": bullets_out,
        })

    # Education: max 2 (single-page)
    educations: list[dict] = []
    for edu in (payload.educations or [])[:2]:
        degree = edu.degree or ""
        if edu.fieldOfStudy:
            degree = f"{degree} in {edu.fieldOfStudy}" if degree else edu.fieldOfStudy
        educations.append({
            "institution": escape_fn(edu.institution or "Institution"),
            "location": escape_fn(edu.location or ""),
            "dates": escape_fn(_format_dates(edu.startYear or "", edu.endYear or "")),
            "degree": escape_fn(degree),
            "grade": escape_fn(edu.grade or ""),
        })

    # Projects: max 2, name + techStack (italic) + description for template layout
    projects: list[dict] = []
    for proj in (payload.projects or [])[:2]:
        desc = _truncate_at_word(proj.description or "", max_len=220)
        projects.append({
            "name": escape_fn(proj.name or "Project"),
            "techStack": escape_fn((proj.techStack or "").strip()),
            "description": escape_fn(desc or ""),
        })

    # Professional summary: JD-optimized from profile (headline, summary, top JD-matching skills)
    professional_summary = _build_professional_summary(
        payload=payload,
        job_title=job_title or "",
        job_description=job_description or "",
        keywords=keywords,
        skills_dict=skills,
        escape_fn=escape_fn,
    )

    # Awards: max 2 (single-page) - only include real awards, no placeholder
    prefs = profile.preferences or {}
    raw_awards = prefs.get("awards", prefs.get("certificates", []))
    if isinstance(raw_awards, list):
        awards = [escape_fn(str(a)) for a in raw_awards if a][:2]
    elif isinstance(raw_awards, str):
        awards = [escape_fn(raw_awards)]
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


def render_html_resume(context: dict, template_dir: Path | None = None) -> str:
    """Render HTML resume from Jinja2 template with context. Returns HTML string."""
    if template_dir is None:
        template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
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


def generate_resume_html(
    db: Session,
    user: User,
    job_title: str,
    job_description: str,
) -> dict:
    """
    Generate resume using Jinja2 HTML template + WeasyPrint.
    Same user profile with JD optimizations (prioritized bullets by keywords).
    Returns: { resume_id, resume_url, presigned_url, resume_name, resume_text }
    """
    profile = ProfileService.get_or_create_profile(db, user)
    context = build_resume_context(profile, job_title or "", job_description or "", for_html=True)

    template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
    html_content = render_html_resume(context, template_dir)

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

    for r in db.query(UserResume).filter(UserResume.user_id == user.id).all():
        r.is_default = 0
    ur = UserResume(
        user_id=user.id,
        resume_url=resume_url,
        resume_name=resume_name,
        resume_text=resume_text,
        is_default=1,
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
    resume_text = build_resume_text_from_payload(profile_model_to_payload(profile))

    # Mark other resumes as non-default
    for r in db.query(UserResume).filter(UserResume.user_id == user.id).all():
        r.is_default = 0
    ur = UserResume(
        user_id=user.id,
        resume_url=resume_url,
        resume_name=resume_name,
        resume_text=resume_text,
        is_default=1,
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
