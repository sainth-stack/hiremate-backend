"""
Job description scraper using Playwright. Renders JS-heavy pages (React, Next.js,
Greenhouse, Lever, Workday, etc.) with a real browser before extracting.

Usage: scrape_job_description_async(url) -> str | None
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from backend.app.services.job_description_cache import get as cache_get, set as cache_set

logger = logging.getLogger(__name__)

# Generic selectors for job description content (works across ATS platforms)
SELECTORS = [
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


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _looks_like_job_description(text: str) -> bool:
    if not text or len(text) < 100:
        return False
    lower = text.lower()
    signals = [
        "experience", "years", "responsibilities", "qualifications", "requirements",
        "role", "skills", "apply", "engineer", "developer",
    ]
    return sum(1 for s in signals if s in lower) >= 2 or "apply" in lower


async def _extract_from_element(handle, selector: str) -> Optional[str]:
    """Get text from element if it matches selector (handles frames/shadow)."""
    try:
        el = await handle.query_selector(selector)
        if not el:
            return None
        text = await el.inner_text()
        normalized = _normalize(text)
        return normalized if len(normalized) > 100 and _looks_like_job_description(normalized) else None
    except Exception:
        return None


async def _extract(page: Page) -> Optional[str]:
    """Extract job description from page (main document, iframes, shadow DOM)."""
    best = None
    best_len = 0

    targets = [page]
    for frame in page.frames():
        if frame != page.main_frame:
            targets.append(frame)

    for target in targets:
        for sel in SELECTORS:
            try:
                text = await _extract_from_element(target, sel)
                if text and len(text) > best_len:
                    best = text
                    best_len = len(text)
            except Exception:
                continue

    return best[:8000] if best else None


async def scrape_job_description_async(url: str, timeout_ms: int = 35000) -> Optional[str]:
    """
    Scrape job description from URL using Playwright.
    Handles all JS-heavy pages (React, Next.js, Greenhouse, Lever, etc.).
    """
    if not url or not url.startswith(("http://", "https://")):
        logger.warning("Invalid URL for scrape: %s", url[:80] if url else "empty")
        return None

    cached = await cache_get(url)
    if cached is not None:
        logger.debug("Cache hit for %s", url[:80])
        return cached

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                await page.wait_for_load_state("networkidle", timeout=25000)
                await asyncio.sleep(2)
            except PlaywrightTimeout:
                pass
            except Exception as e:
                logger.warning("Navigation failed for %s: %s", url[:80], e)
                await browser.close()
                return None

            try:
                await page.wait_for_selector(
                    "text=/responsibilities|requirements|qualifications|experience|about the role|job description/i",
                    timeout=15000,
                )
            except Exception:
                pass

            try:
                result = await _extract(page)
                if result:
                    logger.info("Scraped job description from %s len=%d", url[:80], len(result))
                    await cache_set(url, result)
                    return result
            finally:
                await browser.close()

        return None
    except Exception as e:
        logger.exception("Job description scrape failed: %s", e)
        return None
