"""
Company Job Search — aligned with ``backend`` ATS career stack (no LLM for links/jobs).

- resolve_links: scraped ``career_url`` via ``CareerPageScraper.discover_careers_url``;
  also returns a ``linkedin_search_url`` for users to open manually (not scraped).
- search_jobs_for_company: ``CareerPageScraper.search_jobs`` only — career sites / ATS /
  HTML + inner navigation + optional Playwright. Never scrapes LinkedIn. Results filter by
  ``location`` when set.

``parse_file`` still uses an LLM to extract company names from uploaded PDF/DOCX.
"""

import asyncio
import io
import json
import re
import time
from typing import Any, List, Optional
from urllib.parse import quote_plus

from fastapi import HTTPException

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from backend.app.schemas.company_search import CompanyItem, CompanyLinks, JobEvent, JobResult

logger = get_logger("services.company_search")

MAX_COMPANIES_PER_REQUEST = 100
_semaphore = asyncio.Semaphore(5)
# Per-company ceiling so /links always returns (discovery can be very slow if Google/DDG run first).
_LINKS_DISCOVER_TIMEOUT_SEC = 45.0

_career_scraper = None


def _get_career_scraper():
    """Lazy singleton so ``career_memory.json`` is shared across requests."""
    global _career_scraper
    if _career_scraper is None:
        from backend.app.services.company_search.career import CareerPageScraper

        _career_scraper = CareerPageScraper()
    return _career_scraper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_llm():
    """Return ChatOpenAI if API key set, else None (used by parse_file only)."""
    if not (getattr(settings, "openai_api_key", None) or "").strip():
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=getattr(settings, "openai_model", "gpt-4o-mini") or "gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0,
        )
    except Exception:
        return None


def _extract_text_pdf(contents: bytes) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(stream=contents, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    doc.close()
    return text


def _extract_text_docx(contents: bytes) -> str:
    """
    Extract plain text from a DOCX. python-docx only exposes body-level
    paragraphs via ``doc.paragraphs``; table cell text lives under ``w:tbl``
    and must be walked explicitly (common for company lists).
    """
    import docx
    from docx.document import Document as DocxDocument
    from docx.oxml.ns import qn
    from docx.table import Table, _Cell
    from docx.text.paragraph import Paragraph

    doc = docx.Document(io.BytesIO(contents))

    def iter_block_items(parent):
        if isinstance(parent, DocxDocument):
            body_elm = parent.element.body
        elif isinstance(parent, _Cell):
            body_elm = parent._tc
        else:
            raise ValueError(f"Unexpected parent type: {type(parent)}")
        for child in body_elm:
            if child.tag == qn("w:p"):
                yield Paragraph(child, parent)
            elif child.tag == qn("w:tbl"):
                yield Table(child, parent)

    def table_text(table: Table) -> str:
        lines = []
        for row in table.rows:
            for cell in row.cells:
                for block in iter_block_items(cell):
                    if isinstance(block, Paragraph):
                        t = block.text.strip()
                        if t:
                            lines.append(t)
                    else:
                        nested = table_text(block)
                        if nested.strip():
                            lines.append(nested)
        return "\n".join(lines)

    chunks = []
    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if t:
                chunks.append(t)
        else:
            t = table_text(block)
            if t.strip():
                chunks.append(t)
    return "\n".join(chunks)


def _strip_code_fence(raw: str) -> str:
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def _message_content_to_text(content: Any) -> str:
    """
    LangChain ``AIMessage.content`` may be a str or a list of blocks (e.g. multimodal).
    Calling ``.strip()`` on a list raises AttributeError — that produced 500s on parse.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts).strip()
    return str(content).strip()


def _parse_company_json_array(raw: str) -> list:
    """Parse JSON array from LLM output; tolerate fences and extra prose around ``[...]``."""
    s = _strip_code_fence(raw.strip())
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\[[\s\S]*\]", s)
        if not m:
            logger.warning("parse_file JSON parse failed; snippet=%s", (s[:400] + "…") if len(s) > 400 else s)
            raise ValueError("Could not parse company list from model output (invalid JSON).") from None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise ValueError("Could not parse company list from model output (invalid JSON).") from e
    if not isinstance(data, list):
        raise ValueError("Model must return a JSON array of company objects.")
    return data


async def _resolve_career_url_scraper(company_name: str) -> Optional[str]:
    """Career URL via ``discover_careers_url`` (bounded time so clients do not hang)."""
    async with _semaphore:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_get_career_scraper().discover_careers_url, company_name),
                timeout=_LINKS_DISCOVER_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "discover_careers_url timed out after %.0fs company=%s",
                _LINKS_DISCOVER_TIMEOUT_SEC,
                company_name,
            )
            return None


# ---------------------------------------------------------------------------
# File parsing
# ---------------------------------------------------------------------------

async def parse_file(
    contents: bytes, filename: str, user_id: Optional[int] = None
) -> List[CompanyItem]:
    """Extract company names from a PDF or DOCX file using LLM."""
    if not (getattr(settings, "openai_api_key", None) or "").strip():
        raise HTTPException(status_code=503, detail="OpenAI API key not configured.")

    llm = _get_llm()
    if llm is None:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured.")

    fn_lower = filename.lower()
    if fn_lower.endswith(".pdf"):
        text = _extract_text_pdf(contents)
    elif fn_lower.endswith(".docx"):
        text = _extract_text_docx(contents)
    else:
        raise ValueError(f"Unsupported file type: {filename}")

    if not (text or "").strip():
        raise ValueError(
            "No text could be read from the file. "
            "If this is a DOCX, ensure it is not empty, password-protected, "
            "or .doc saved as .docx incorrectly."
        )

    prompt = (
        "Extract all company names from the document text below.\n"
        'Return a JSON array of objects with "name" (string) and "section" '
        '(string or null, e.g. "FAANG", "Startups", "Dream Companies").\n'
        "Return ONLY the JSON array with no explanation.\n\n"
        f"Document:\n{text[:8000]}"
    )

    t0 = time.monotonic()
    from langchain_core.messages import HumanMessage

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
    except Exception as exc:
        logger.warning("parse_file LLM request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI request failed while extracting companies: {exc!s}",
        ) from exc

    raw_text = _message_content_to_text(getattr(response, "content", None))
    if not raw_text:
        raise HTTPException(status_code=502, detail="Empty response from language model.")

    try:
        data = _parse_company_json_array(raw_text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    results: List[CompanyItem] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name or not isinstance(name, str):
            continue
        sec = item.get("section")
        section_out: Optional[str] = sec if isinstance(sec, str) else None
        results.append(CompanyItem(name=name.strip(), section=section_out))

    if not results:
        raise HTTPException(
            status_code=422,
            detail="No company names could be read from the model output. Try a clearer document or shorter list.",
        )

    logger.info(
        "parse_file user_id=%s company_count=%d duration_ms=%d",
        user_id, len(results), int((time.monotonic() - t0) * 1000),
    )
    return results


# ---------------------------------------------------------------------------
# Link resolution  ← main fix
# ---------------------------------------------------------------------------

async def resolve_links(
    companies: List[CompanyItem],
    role: str,
    location: str,
    user_id: Optional[int] = None,
) -> List[CompanyLinks]:
    """
    Resolve career URLs with ``CareerPageScraper.discover_careers_url`` (fast path:
    common ``careers.`` / ``/careers`` patterns, then sitemap/homepage, then DDG API,
    then legacy HTML search). Each company is capped at ~45s so the response is not
    blocked by slow search engines.

    Also builds a LinkedIn job-search URL per company for **manual** use in the UI.
    Automated job streaming (`/jobs/stream`) never scrapes LinkedIn — only career sites.

    ``role`` / ``location`` refine the LinkedIn search link and the career-site job search.
    """
    t0 = time.monotonic()

    career_urls: List[Optional[str]] = await asyncio.gather(
        *[_resolve_career_url_scraper(c.name) for c in companies]
    )

    results: List[CompanyLinks] = []
    for company, career_url in zip(companies, career_urls):
        keywords = (
            quote_plus(f"{company.name} {role}".strip()) if role else quote_plus(company.name)
        )
        li_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}"
        if location:
            li_url += f"&location={quote_plus(location)}"

        results.append(
            CompanyLinks(
                name=company.name,
                career_url=career_url,
                linkedin_search_url=li_url,
            )
        )

    logger.info(
        "resolve_links user_id=%s company_count=%d found_career_urls=%d duration_ms=%d",
        user_id,
        len(results),
        sum(1 for r in results if r.career_url),
        int((time.monotonic() - t0) * 1000),
    )
    return results


# ---------------------------------------------------------------------------
# Job search (CareerPageScraper only — same as backend ATS career flow)
# ---------------------------------------------------------------------------

async def search_jobs_for_company(
    company: CompanyLinks,
    role: str,
    skills: List[str],
    location: str,
    user_id: Optional[int] = None,
) -> JobEvent:
    """
    Open listings via ``CareerPageScraper.search_jobs`` (memory + discovery + ATS +
    HTML + optional Playwright). Does **not** scrape or call LinkedIn; ``linkedin_search_url``
    is only for the UI. Jobs are filtered by ``location`` when non-empty (matched against
    scraped job location strings).
    """
    skills = skills or []
    t0 = time.monotonic()

    try:
        async with _semaphore:
            ats_jobs = await asyncio.to_thread(
                _get_career_scraper().search_jobs,
                company.name,
                role or "",
                skills,
                location or "",
            )
    except Exception as exc:
        logger.warning("CareerPageScraper.search_jobs failed for %s: %s", company.name, exc)
        return JobEvent(
            company=company.name,
            jobs=[],
            status="error",
            message=str(exc),
        )

    if not ats_jobs:
        logger.info(
            "search_jobs_for_company user_id=%s company=%s job_count=0",
            user_id,
            company.name,
        )
        hint = (
            "No roles matched your location filter on the career site listings."
            if (location or "").strip()
            else "No open roles matched the scraper filters for this company."
        )
        return JobEvent(
            company=company.name,
            jobs=[],
            status="done",
            message=hint,
        )

    jobs = [
        JobResult(
            title=j.role,
            url=j.apply_url,
            location=j.location,
            snippet=(j.description[:800] if j.description else None),
        )
        for j in ats_jobs[:15]
    ]
    logger.info(
        "search_jobs_for_company user_id=%s company=%s job_count=%d duration_ms=%d",
        user_id,
        company.name,
        len(jobs),
        int((time.monotonic() - t0) * 1000),
    )
    return JobEvent(company=company.name, jobs=jobs, status="done")