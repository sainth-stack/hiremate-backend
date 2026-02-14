"""
Job description scraper using Playwright for JS-heavy sites (React, Next.js, Greenhouse, Lever, etc.).

Playwright renders pages with a real Chromium browser, so we get fully executed JavaScript
before extracting. This handles:
- React/Next.js client-side rendering
- Infinite scroll
- Dynamic API-loaded content
- Greenhouse, Lever, Workday, Workable, custom ATS

Usage: scrape_job_description_async(url) -> str | None
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from backend.app.services.job_description_cache import get as cache_get, set as cache_set

logger = logging.getLogger(__name__)

# Same selectors as extension + common ATS patterns (Greenhouse, Lever, Workday, etc.)
JOB_DESC_SELECTORS = [
    "[data-automation-id='jobDescription']",
    "[data-automation-id='job-description']",
    "[data-testid*='job-description']",
    "[data-testid*='jobDescription']",
    ".job-description",
    ".job-description-content",
    ".posting-description",
    ".job-posting",
    ".job-details",
    ".job-body",
    ".job-content",
    ".jd-content",
    "[class*='job-description']",
    "[class*='jobDescription']",
    "[class*='job-detail']",
    "[class*='job-content']",
    "[data-automation-id='job-posting']",
    "#job-description",
    "#jobDescription",
    "[id*='job-description']",
    "[id*='jobDescription']",
    "section[class*='job']",
    "[class*='description']",
    ".description",
    ".content",
    "#content",
    "article",
    "[role='main']",
    "main",
]

# ATS-specific selectors
ATS_SELECTORS = {
    "greenhouse": [".content", "#content", "[class*='content']"],
    "lever": [".posting-page", ".posting-description", ".content"],
    "workday": ["[data-automation-id='jobPosting']", "[data-automation-id='jobPostingDescription']"],
    "workable": [".job-body", ".job-description"],
}


def _looks_like_job_description(text: str) -> bool:
    """Heuristic: does this text look like a job description?"""
    if not text or len(text) < 50:
        return False
    lower = text.lower()
    signals = [
        "experience", "years", "responsibilities", "qualifications", "requirements",
        "role", "skills", "apply", "engineer", "developer", "python", "java",
    ]
    matches = sum(1 for s in signals if s in lower)
    return matches >= 2 or "apply" in lower or "responsibilities" in lower


def _normalize_text(text: str) -> str:
    """Normalize whitespace and trim."""
    return re.sub(r"\s+", " ", (text or "").strip())


async def _extract_from_page(page: Page) -> Optional[str]:
    """Extract job description from a rendered page using selectors."""
    for sel in JOB_DESC_SELECTORS:
        try:
            el = await page.query_selector(sel)
            if el:
                text = await el.inner_text()
                normalized = _normalize_text(text)
                if len(normalized) > 100 and _looks_like_job_description(normalized):
                    return normalized[:8000]
        except Exception:
            continue

    # Try ATS-specific selectors based on URL
    url = page.url.lower()
    for ats, selectors in ATS_SELECTORS.items():
        if ats in url:
            for sel in selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        normalized = _normalize_text(text)
                        if len(normalized) > 100:
                            return normalized[:8000]
                except Exception:
                    continue

    # Fallback: main content area
    for sel in ["main", "[role='main']", "article", ".content", "#content", "body"]:
        try:
            el = await page.query_selector(sel)
            if el:
                text = await el.inner_text()
                normalized = _normalize_text(text)
                if len(normalized) >= 200 and _looks_like_job_description(normalized):
                    return normalized[:8000]
        except Exception:
            continue

    return None


async def _scrape_async(url: str, timeout_ms: int = 25000) -> Optional[str]:
    """Scrape job description from URL using Playwright (async)."""
    if not url or not url.startswith(("http://", "https://")):
        logger.warning("Invalid URL for scrape: %s", url[:80] if url else "empty")
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        try:
            # Navigate and wait for content
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Extra wait for JS-heavy SPAs to render
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            logger.warning("Page load timeout for %s, trying with current content", url[:80])
        except Exception as e:
            logger.warning("Navigation failed for %s: %s", url[:80], e)
            await browser.close()
            return None

        try:
            result = await _extract_from_page(page)
            if result:
                logger.info("Scraped job description from %s len=%d", url[:80], len(result))
            return result
        finally:
            await browser.close()


async def scrape_job_description_async(url: str, timeout_ms: int = 25000) -> Optional[str]:
    """
    Scrape job description from a URL using Playwright (async).
    Uses in-memory cache to avoid re-scraping; cache TTL 1h, max 500 entries.

    Renders the page with headless Chromium (executes JavaScript) before extracting.
    Works with Greenhouse, Lever, Workday, React/Next.js career sites, etc.

    Returns job description text (up to 8000 chars) or None on failure.
    """
    cached = await cache_get(url)
    if cached is not None:
        logger.debug("Cache hit for %s", url[:80])
        return cached

    try:
        result = await _scrape_async(url, timeout_ms)
        if result:
            await cache_set(url, result)
        return result
    except Exception as e:
        logger.exception("Job description scrape failed: %s", e)
        return None


