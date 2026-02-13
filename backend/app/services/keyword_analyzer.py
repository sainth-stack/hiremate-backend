"""
Keyword analysis: extract skills from job description, match against resume.
Uses LLM for accurate extraction, fast Python for matching. Minimal, cached.
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

logger = logging.getLogger(__name__)
_OPENAI_CLIENT: OpenAI | None = None
_CACHE_TTL = 600
_CACHE: dict[str, tuple[float, dict]] = {}
_MAX_ENTRIES = 128

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
    "kubernetes": ["kubernetes", "k8s"],
    "machine learning": ["machine learning", "ml"],
    "artificial intelligence": ["artificial intelligence", "ai"],
    "c++": ["c++", "cpp"],
    "c#": ["c#", "csharp"],
}

EXTRACT_PROMPT = """Extract skills/technologies from this job description.

Return JSON only:
{"high_priority":["skill1","skill2",...],"low_priority":["skill1",...]}

Rules:
- high_priority: core required skills (frameworks, languages, key tech). Max 25.
- low_priority: nice-to-have, secondary skills. Max 15.
- Single words or 2-word phrases. Normalize: "React.js"→"React", "Node.js"→"Node".
- No duplicates. Lowercase. Be concise.

Job description:
"""


def _get_client() -> OpenAI:
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        _OPENAI_CLIENT = OpenAI(api_key=settings.openai_api_key)
    return _OPENAI_CLIENT


def _hash_input(jd: str, resume: str) -> str:
    return hashlib.sha256((jd[:4000] + "|||" + resume[:4000]).encode()).hexdigest()[:32]


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
    split = min(20, len(skills) // 2) if skills else 0
    return {"high_priority": skills[:split] or skills[:15], "low_priority": skills[split:][:10]}


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
        high = [str(k).strip().lower() for k in data.get("high_priority", []) if k][:25]
        low = [str(k).strip().lower() for k in data.get("low_priority", []) if k][:15]
        return {"high_priority": high, "low_priority": low}
    except Exception as e:
        logger.warning("LLM keyword extract failed: %s, using fallback", e)
        return _extract_keywords_fallback(jd)


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
    cached = _CACHE.get(cache_key)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        logger.info("Keyword analysis cache hit")
        return cached[1]

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

    extracted = _extract_keywords_llm(jd)
    high = extracted.get("high_priority", [])
    low = extracted.get("low_priority", [])

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

    result = {
        "total_keywords": total,
        "matched_count": matched,
        "percent": percent,
        "high_priority": high_matched,
        "low_priority": low_matched,
    }

    if len(_CACHE) >= _MAX_ENTRIES:
        oldest = min(_CACHE.items(), key=lambda x: x[1][0])[0]
        _CACHE.pop(oldest, None)
    _CACHE[cache_key] = (time.time(), result)

    logger.info(
        "Keyword analysis done total=%d matched=%d percent=%d ms=%d",
        total,
        matched,
        percent,
        int((time.monotonic() - started) * 1000),
    )
    return result
