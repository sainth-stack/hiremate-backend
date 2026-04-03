"""
Company Job Search service — file parsing and link resolution.
"""
import asyncio
import io
import json
import time
from typing import List, Optional
from urllib.parse import quote_plus

from fastapi import HTTPException

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from backend.app.schemas.company_search import CompanyItem, CompanyLinks, JobEvent, JobResult

logger = get_logger("services.company_search")

MAX_COMPANIES_PER_REQUEST = 100
_semaphore = asyncio.Semaphore(5)


def _get_llm():
    """Return ChatOpenAI if API key set, else None."""
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
    import docx
    doc = docx.Document(io.BytesIO(contents))
    return "\n".join(p.text for p in doc.paragraphs)


def _strip_code_fence(raw: str) -> str:
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


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

    prompt = (
        "Extract all company names from the document text below.\n"
        'Return a JSON array of objects with "name" (string) and "section" '
        '(string or null, e.g. "FAANG", "Startups", "Dream Companies").\n'
        "Return ONLY the JSON array with no explanation.\n\n"
        f"Document:\n{text[:8000]}"
    )

    t0 = time.monotonic()
    from langchain_core.messages import HumanMessage
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    data = json.loads(_strip_code_fence(response.content.strip()))
    results = [CompanyItem(name=item["name"], section=item.get("section")) for item in data]
    logger.info(
        "parse_file user_id=%s company_count=%d duration_ms=%d",
        user_id, len(results), int((time.monotonic() - t0) * 1000),
    )
    return results


async def resolve_links(
    companies: List[CompanyItem], role: str, location: str, user_id: Optional[int] = None
) -> List[CompanyLinks]:
    """Batch LLM call to find official careers URL per company; build LinkedIn search URLs."""
    if not (getattr(settings, "openai_api_key", None) or "").strip():
        raise HTTPException(status_code=503, detail="OpenAI API key not configured.")

    llm = _get_llm()
    if llm is None:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured.")

    names = [c.name for c in companies]
    prompt = (
        "For each company below, provide its official careers/jobs page URL.\n"
        'Return a JSON array of objects with "name" (string) and "career_url" (string or null).\n'
        "Return ONLY the JSON array with no explanation.\n\n"
        f"Companies:\n{json.dumps(names)}"
    )

    t0 = time.monotonic()
    from langchain_core.messages import HumanMessage
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    data = json.loads(_strip_code_fence(response.content.strip()))
    career_map = {item["name"]: item.get("career_url") for item in data}

    results = []
    for company in companies:
        keywords = quote_plus(f"{role} {company.name}".strip()) if role else quote_plus(company.name)
        li_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}"
        if location:
            li_url += f"&location={quote_plus(location)}"
        results.append(
            CompanyLinks(
                name=company.name,
                career_url=career_map.get(company.name),
                linkedin_search_url=li_url,
            )
        )
    logger.info(
        "resolve_links user_id=%s company_count=%d duration_ms=%d",
        user_id, len(results), int((time.monotonic() - t0) * 1000),
    )
    return results


async def search_jobs_for_company(
    company: CompanyLinks,
    role: str,
    skills: List[str],
    location: str,
    user_id: Optional[int] = None,
) -> JobEvent:
    """Search for open roles at a company using an LLM with web search grounding."""
    if not (getattr(settings, "openai_api_key", None) or "").strip():
        raise HTTPException(status_code=503, detail="OpenAI API key not configured.")

    skills_str = ", ".join(skills) if skills else "general"
    prompt = (
        f"Search for 3–5 current open job listings at {company.name}"
        + (f" matching the role '{role}'" if role else "")
        + (f" in {location}" if location else "")
        + f". Prioritise roles related to these skills: {skills_str}.\n"
        "Return ONLY valid JSON in this exact shape, no explanation:\n"
        '{"jobs": [{"title": "...", "url": "...", "location": "...", "snippet": "..."}]}'
    )

    t0 = time.monotonic()
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        async with _semaphore:
            response = await client.responses.create(
                model=settings.openai_model or "gpt-4o-mini",
                tools=[{"type": "web_search_preview"}],
                input=prompt,
            )
        # Extract text from the response output
        raw = ""
        for block in response.output:
            if getattr(block, "type", None) == "message":
                for part in block.content:
                    if getattr(part, "type", None) == "output_text":
                        raw = part.text
                        break
            if raw:
                break

        data = json.loads(_strip_code_fence(raw))
        jobs = [
            JobResult(
                title=j.get("title", ""),
                url=j.get("url"),
                location=j.get("location"),
                snippet=j.get("snippet"),
            )
            for j in data.get("jobs", [])
        ]
        logger.info(
            "search_jobs_for_company user_id=%s company=%s job_count=%d duration_ms=%d",
            user_id, company.name, len(jobs), int((time.monotonic() - t0) * 1000),
        )
        return JobEvent(company=company.name, jobs=jobs, status="done")
    except Exception as exc:
        logger.warning("search_jobs_for_company failed for %s: %s", company.name, exc)
        return JobEvent(company=company.name, jobs=[], status="error", message=str(exc))
