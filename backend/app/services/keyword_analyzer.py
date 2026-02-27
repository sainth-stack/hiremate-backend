"""
Keyword analysis: extract skills from job description, match against resume.
Uses LLM for accurate extraction, fast Python for matching. Cached via analysis_cache.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any

from openai import OpenAI

from backend.app.core.config import settings
from backend.app.services.analysis_cache import get as cache_get, set as cache_set

logger = logging.getLogger(__name__)
_OPENAI_CLIENT: OpenAI | None = None

# Two-tier cache: extraction by JD (skip LLM on same JD), full result by (JD, resume)
_extraction_cache: dict[str, tuple[float, dict]] = {}

# Tech aliases for match accuracy (resume may say "React.js", JD says "React")
_ALIASES: dict[str, list[str]] = {
    "react": ["react", "react.js", "reactjs"],
    "reactjs": ["react", "react.js", "reactjs"],
    "node": ["node", "node.js", "nodejs"],
    "nodejs": ["node", "node.js", "nodejs"],
    "javascript": ["javascript", "js"],
    "js": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "ts": ["typescript", "ts"],
    "python": ["python", "py"],
    "vue": ["vue", "vue.js", "vuejs"],
    "angular": ["angular", "angularjs", "angular.js"],
    "mongodb": ["mongodb", "mongo"],
    "postgresql": ["postgresql", "postgres", "psql"],
    "rest": ["rest", "rest api", "restful"],
    "rest api": ["rest", "rest api", "restful"],
    "kubernetes": ["kubernetes", "k8s"],
    "machine learning": ["machine learning", "ml"],
    "artificial intelligence": ["artificial intelligence", "ai"],
    "c++": ["c++", "cpp"],
    "c#": ["c#", "csharp"],
}

EXTRACT_PROMPT = """Extract ONLY the most important technical skills from this job description.
These are skills recruiters/hiring managers actually screen for.

Return JSON only:
{"high_priority":["skill1","skill2",...],"low_priority":["skill1",...]}

Rules:
- high_priority: MUST-HAVE skills. Languages (JavaScript, Python), frameworks (React, Node.js), databases (Postgres, MongoDB), tools (Git, CI/CD). Max 12.
- low_priority: Nice-to-have only. Max 8.
- Be strict: extract only concrete tech recruiters filter on. Normalize: "React.js"→"React", "REST API"→"REST API".
- EXCLUDE: vague terms like "documentation", "components", "libraries", "maintainability", "ui", "ux", "performance", "scalability", "deployment", "architecture", "testing", "code review", "debugging", "design", "integration", "mentoring", "collaboration", "troubleshooting", "enterprise", "cms", "toolsets", "business teams", "customer experience", "systems thinking".
- Single words or 2-word phrases. Lowercase. No duplicates.

Job description:
"""

# Filter out vague terms (not concrete tech recruiters screen for)
_EXCLUDED_KEYWORDS = frozenset({
    "documentation", "components", "libraries", "maintainability", "ui", "ux",
    "performance", "scalability", "deployment", "architecture", "code review",
    "debugging", "design", "integration", "mentoring", "collaboration",
    "troubleshooting", "enterprise", "cms", "toolsets", "business teams",
    "customer experience", "systems thinking",
})


def _get_client() -> OpenAI:
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        _OPENAI_CLIENT = OpenAI(api_key=settings.openai_api_key)
    return _OPENAI_CLIENT


def _hash_input(jd: str, resume: str) -> str:
    return hashlib.sha256((jd[:4000] + "|||" + resume[:4000]).encode()).hexdigest()[:32]


def _hash_jd(jd: str) -> str:
    return hashlib.sha256(jd[:4000].encode()).hexdigest()[:24]


def _get_aliases(kw: str) -> list[str]:
    k = kw.lower().strip()
    for base, alts in _ALIASES.items():
        if k in alts or k == base:
            return list(set([base] + alts))
    return [k]


def _resume_contains(resume_lower: str, keyword: str) -> bool:
    """Check if resume contains keyword (with alias expansion)."""
    if not keyword or len(keyword) < 2:
        return False
    kw = keyword.lower().strip()
    if kw in resume_lower:
        return True
    for alt in _get_aliases(kw):
        if alt in resume_lower:
            return True
    # Word boundary for short terms (e.g. "C#" vs "C")
    if len(kw) >= 3:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, resume_lower):
            return True
    return False


def _extract_keywords_fallback(jd: str) -> dict[str, list[str]]:
    """Fast regex fallback when LLM unavailable."""
    text = re.sub(r"[^a-z0-9\s\-+#./]", " ", jd.lower())
    words = re.findall(r"[a-z0-9#+]{2,}(?:\.[a-z0-9]+)?", text)
    stop = {"the", "and", "for", "with", "that", "this", "from", "have", "been", "will", "your", "you"}
    seen = set()
    skills = []
    for w in words:
        if w not in stop and w not in seen and not w.isdigit():
            seen.add(w)
            skills.append(w)
    split = min(12, len(skills) // 2) if skills else 0
    return {"high_priority": skills[:split] or skills[:12], "low_priority": skills[split:][:6]}


def _extract_keywords(job_description: str) -> dict[str, list[str]]:
    """Extract keywords from JD. Uses extraction cache to skip LLM when same JD."""
    jd = (job_description or "").strip()[:3500]
    if not jd or len(jd) < 80:
        return {"high_priority": [], "low_priority": []}

    jd_key = _hash_jd(jd)
    now = time.time()
    if jd_key in _extraction_cache:
        ts, val = _extraction_cache[jd_key]
        if now - ts < settings.keyword_extraction_ttl:
            logger.debug("Keyword extraction cache hit (same JD)")
            return val
        del _extraction_cache[jd_key]

    result = _extract_keywords_llm(job_description)
    while len(_extraction_cache) >= settings.keyword_extraction_max_entries and _extraction_cache:
        oldest = min(_extraction_cache.items(), key=lambda x: x[1][0])[0]
        del _extraction_cache[oldest]
    _extraction_cache[jd_key] = (now, result)
    return result


def _extract_keywords_llm(job_description: str) -> dict[str, list[str]]:
    jd = (job_description or "").strip()[:3500]
    if not jd or len(jd) < 80:
        return {"high_priority": [], "low_priority": []}

    if not settings.openai_api_key:
        return _extract_keywords_fallback(jd)

    client = _get_client()
    prompt = EXTRACT_PROMPT + jd

    try:
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )
        content = (resp.choices[0].message.content or "").strip()
        content = re.sub(r"^```\w*\n?", "", content).replace("```", "").strip()
        data = json.loads(content)
        high = [str(k).strip().lower() for k in data.get("high_priority", []) if k][:12]
        low = [str(k).strip().lower() for k in data.get("low_priority", []) if k][:6]
        return {"high_priority": high, "low_priority": low}
    except Exception as e:
        logger.warning("LLM keyword extract failed: %s, using fallback", e)
        return _extract_keywords_fallback(jd)


def extract_keywords_for_resume(job_description: str) -> dict[str, list[str]]:
    """
    Extract keywords from JD using same logic as analyze_keywords.
    Use this in resume generation to ensure the resume targets the exact keywords
    the extension's analyze API will check. Returns {high_priority, low_priority}.
    """
    return _extract_keywords(job_description)


def analyze_keywords(job_description: str, resume_text: str) -> dict[str, Any]:
    """
    Analyze job description vs resume. Returns match stats and keyword lists.
    Cached by (jd, resume) hash. Uses LLM for extraction, fast Python for matching.
    """
    started = time.monotonic()
    jd = (job_description or "").strip()[:4000]
    resume = (resume_text or "").strip()[:8000]
    resume_lower = resume.lower()

    cache_key = _hash_input(jd, resume)
    cached = cache_get(cache_key)
    if cached:
        logger.info("Keyword analysis cache hit")
        return cached

    if not jd or len(jd) < 50:
        return {
            "total_keywords": 0,
            "matched_count": 0,
            "percent": 0,
            "high_priority": [],
            "low_priority": [],
            "message": "Job description too short",
        }

    if not resume:
        return {
            "total_keywords": 0,
            "matched_count": 0,
            "percent": 0,
            "high_priority": [],
            "low_priority": [],
            "message": "No resume text",
        }

    extracted = _extract_keywords(jd)
    high = [k for k in extracted.get("high_priority", []) if k and k not in _EXCLUDED_KEYWORDS]
    low = [k for k in extracted.get("low_priority", []) if k and k not in _EXCLUDED_KEYWORDS]

    def match_list(kw_list: list[str]) -> list[dict[str, Any]]:
        out = []
        for kw in kw_list:
            if not kw:
                continue
            matched = _resume_contains(resume_lower, kw)
            out.append({"keyword": kw.title(), "matched": matched})
        return out

    high_matched = match_list(high)
    low_matched = match_list(low)

    all_kw = high + low
    total = len(all_kw)
    matched = sum(1 for m in high_matched + low_matched if m["matched"])
    percent = round((matched / total) * 100) if total else 0

    message = None
    if total == 0 and jd and len(jd) > 100:
        message = "No technical skills found. The content may be salary/benefits only. Scroll for the full job description with requirements."

    result = {
        "total_keywords": total,
        "matched_count": matched,
        "percent": percent,
        "high_priority": high_matched,
        "low_priority": low_matched,
        "message": message,
    }

    cache_set(cache_key, result)

    logger.info(
        "Keyword analysis done total=%d matched=%d percent=%d ms=%d",
        total,
        matched,
        percent,
        int((time.monotonic() - started) * 1000),
    )
    return result
