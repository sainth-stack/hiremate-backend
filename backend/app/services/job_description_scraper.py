"""
Parse job description from client-scraped HTML.
Extension sends page_html from all frames (main + iframes). Backend parses and extracts JD.

Strategy (in order):
1. JSON-LD <script type="application/ld+json"> with JobPosting schema
2. Next.js <script id="__NEXT_DATA__"> JSON blob (Tekion, Greenhouse, Lever, etc.)
3. CSS selector matching against known JD containers
4. DOM walk scoring heuristic
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from bs4 import BeautifulSoup

from backend.app.core.config import FRAME_SEP, MAX_HTML_BYTES

logger = logging.getLogger(__name__)

SELECTORS = [
    # Workday
    "[data-automation-id='jobDescription']",
    "[data-automation-id='job-description']",
    "[data-automation-id='job-posting']",
    # Lever / Greenhouse
    ".content",
    ".posting-description",
    ".posting-header",
    # Generic
    ".job-description",
    ".content--text",
    "[class*='job-description']",
    "[class*='jobDescription']",
    "[data-testid*='job-description']",
    "[data-testid*='jobDescription']",
    ".job-description-content",
    ".job-posting",
    ".job-details",
    ".job-body",
    ".job-content",
    "#job-description",
    "#jobDescription",
    "[id*='job-description']",
    "section[class*='job']",
    "[class*='description']",
    ".description",
    # Next.js / React CSS module patterns (e.g. job_Root__xxxx, job_Embedded__xxxx)
    "[class*='job_']",
    "[class*='Job']",
    # Wide fallbacks
    "[id='content']",
    "article",
    "[role='main']",
    "main",
]

_JD_DICT_KEYS = [
    "jobDescription", "job_description", "description", "body",
    "content", "responsibilities", "overview", "jobPosting",
    "fullDescription", "full_description", "descriptionHtml",
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _element_likely_hidden(tag) -> bool:
    if not tag or not hasattr(tag, "get"):
        return True
    if tag.get("hidden") is not None or tag.get("aria-hidden") == "true":
        return True
    style = (tag.get("style") or "").lower().replace(" ", "")
    return "display:none" in style or "visibility:hidden" in style


def _is_salary_disclaimer_only(text: str) -> bool:
    """Reject blocks that are purely salary/compensation disclaimers with no job requirements."""
    if not text or len(text) < 200:
        return False
    lower = text.lower()
    salary_start = "the salary range describes" in lower or "salary range describes" in lower
    has_compensation = "compensation offered" in lower or "base salary" in lower or "hiring range" in lower
    has_jd = any(k in lower for k in [
        "responsibilities", "requirements", "qualifications", "about the role",
        "what you'll do", "key responsibilities", "you will",
    ])
    if salary_start and has_compensation and not has_jd:
        return True
    if "geographic location" in lower and "equity compensation" in lower and "recruiter can share" in lower:
        return True
    return False


def _score_text(text: str) -> int:
    """Score how likely text is a job description. Returns int score."""
    if not text:
        return 0
    lower = text.lower()
    positive = [
        "responsibilities", "requirements", "qualifications", "experience",
        "skills", "role", "job description", "about the role", "engineer",
        "developer", "what you", "you will", "you'll", "join us",
        "manager", "analyst", "architect", "lead",
    ]
    negative = [
        "privacy policy", "cookie policy", "sign up", "login",
        "similar jobs", "subscribe", "newsletter", "all rights reserved",
    ]
    score = sum(2 for k in positive if k in lower)
    score -= sum(3 for k in negative if k in lower)

    # Bullet points in raw (un-normalized) OR normalized text
    # After _normalize whitespace is collapsed but bullets like "• item" still exist
    if re.search(r"[•●▪▸\-\*]\s+\w", text):
        count = len(re.findall(r"[•●▪▸\-\*]\s+\w", text))
        if count > 3:
            score += 3
    # Newline-separated bullets (pre-normalization text)
    elif re.search(r"\n\s*[-•●*]", text):
        score += 3

    return score


def _looks_like_job_description(text: str) -> bool:
    if not text or len(text) < 300:
        return False
    if _is_salary_disclaimer_only(text):
        return False
    return _score_text(text) >= 3


def _html_fragment_to_text(html_str: str) -> str:
    """Convert an HTML fragment (e.g. from JSON-LD description) to plain text."""
    try:
        soup = BeautifulSoup(html_str, "html.parser")
        return _normalize(soup.get_text(separator=" ", strip=True))
    except Exception:
        return _normalize(html_str)


# ---------------------------------------------------------------------------
# Phase 1: JSON-LD structured data
# ---------------------------------------------------------------------------

def _extract_from_json_ld(soup: BeautifulSoup) -> Optional[str]:
    """Try to extract job description from JSON-LD JobPosting schema."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = (script.string or "").strip()
            if not raw:
                continue
            data = json.loads(raw)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") in ("JobPosting", "jobPosting"):
                    desc = item.get("description") or item.get("responsibilities") or ""
                    if desc and len(desc) >= 200:
                        text = _html_fragment_to_text(desc)
                        if len(text) >= 200:
                            return text[:8000]
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Phase 2: Next.js __NEXT_DATA__ JSON blob
# ---------------------------------------------------------------------------

def _find_jd_in_obj(obj: Any, depth: int = 0) -> Optional[str]:
    """Recursively search a JSON object for a job description string."""
    if depth > 12:
        return None
    if isinstance(obj, str):
        if len(obj) >= 400 and _looks_like_job_description(obj):
            return _html_fragment_to_text(obj)[:8000]
        return None
    if isinstance(obj, dict):
        # Check priority keys first
        for key in _JD_DICT_KEYS:
            val = obj.get(key)
            if isinstance(val, str) and len(val) >= 200:
                text = _html_fragment_to_text(val)
                if _looks_like_job_description(text):
                    return text[:8000]
        # Recurse
        best: Optional[str] = None
        for val in obj.values():
            result = _find_jd_in_obj(val, depth + 1)
            if result and (not best or len(result) > len(best)):
                best = result
        return best
    if isinstance(obj, list):
        best = None
        for item in obj:
            result = _find_jd_in_obj(item, depth + 1)
            if result and (not best or len(result) > len(best)):
                best = result
        return best
    return None


def _extract_from_next_data(soup: BeautifulSoup) -> Optional[str]:
    """Try to extract job description from Next.js __NEXT_DATA__ JSON."""
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        return None
    try:
        data = json.loads(script.string or "")
        return _find_jd_in_obj(data)
    except Exception as e:
        logger.debug("__NEXT_DATA__ parse failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Phase 3: CSS selectors
# ---------------------------------------------------------------------------

def _extract_from_selectors(body) -> Optional[str]:
    best, best_len = None, 0
    for sel in SELECTORS:
        try:
            for el in body.select(sel):
                if _element_likely_hidden(el):
                    continue
                raw_text = el.get_text(separator=" ", strip=True) or ""
                text = _normalize(raw_text)
                if len(text) >= 300 and _looks_like_job_description(text) and len(text) > best_len:
                    best, best_len = text, len(text)
        except Exception:
            continue
    return best[:8000] if best else None


# ---------------------------------------------------------------------------
# Phase 4: DOM walk heuristic
# ---------------------------------------------------------------------------

def _extract_from_dom_walk(body) -> Optional[str]:
    skip_tags = {"script", "style", "nav", "footer", "header", "aside", "noscript"}
    candidates: list[tuple[str, int]] = []

    def walk(node):
        if not node or not hasattr(node, "name") or node.name is None:
            return
        tag = (node.name or "").lower()
        if tag in skip_tags:
            return
        cls = " ".join(node.get("class") or []).lower()
        nid = (node.get("id") or "").lower()
        is_candidate = (
            tag in ("article", "main", "section")
            or any(kw in cls for kw in ["job", "description", "content", "posting", "detail"])
            or any(kw in nid for kw in ["job", "description", "content", "posting"])
        )
        if is_candidate:
            raw_text = node.get_text(separator=" ", strip=True) or ""
            text = _normalize(raw_text)
            if len(text) >= 300 and not _is_salary_disclaimer_only(text):
                score = _score_text(text)
                if score >= 2:
                    candidates.append((text, score))
        for child in getattr(node, "children", []) or []:
            if hasattr(child, "name"):
                walk(child)

    walk(body)
    if not candidates:
        return None
    best_match = max(candidates, key=lambda x: (x[1], len(x[0])))
    return best_match[0][:8000]


# ---------------------------------------------------------------------------
# Core parsing
# ---------------------------------------------------------------------------

def _parse_single_html(html: str) -> Optional[str]:
    """Parse one HTML blob. Returns job description text or None."""
    if not html or len(html) < 100:
        return None
    html = html.strip()[:MAX_HTML_BYTES]
    try:
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("body") or soup

        # Phase 1: JSON-LD (fastest and most structured)
        result = _extract_from_json_ld(soup)
        if result and len(result) >= 100:
            logger.debug("JD extracted via JSON-LD (%d chars)", len(result))
            return result

        # Phase 2: Next.js __NEXT_DATA__
        result = _extract_from_next_data(soup)
        if result and len(result) >= 100:
            logger.debug("JD extracted via __NEXT_DATA__ (%d chars)", len(result))
            return result

        if not body:
            return None

        # Phase 3: CSS selectors
        result = _extract_from_selectors(body)
        if result and len(result) >= 100:
            logger.debug("JD extracted via selectors (%d chars)", len(result))
            return result

        # Phase 4: DOM walk
        result = _extract_from_dom_walk(body)
        if result and len(result) >= 100:
            logger.debug("JD extracted via DOM walk (%d chars)", len(result))
            return result

        return None
    except Exception as e:
        logger.debug("_parse_single_html failed: %s", e)
        return None


def parse_job_description_from_html(html: str) -> Optional[str]:
    """
    Parse job description from client-scraped page_html.
    Handles combined HTML from multiple frames (split by FRAME_SEP).
    Returns best JD found across all frames (longest valid result).
    """
    if not html or not isinstance(html, str) or len(html.strip()) < 100:
        return None
    chunks = [c.strip() for c in html.split(FRAME_SEP) if c.strip() and len(c.strip()) > 100]
    if not chunks:
        chunks = [html]

    best: Optional[str] = None
    for chunk in chunks:
        jd = _parse_single_html(chunk)
        if jd and len(jd) >= 50:
            if not best or len(jd) > len(best):
                best = jd
    return best
