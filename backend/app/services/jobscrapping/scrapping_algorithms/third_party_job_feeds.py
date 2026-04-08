"""
Best-effort job discovery from public surfaces (RSS / HTML).

Indeed: official RSS by search query. LinkedIn / Naukri: fragile HTML/guest-API parsing — may break
when sites change; respect robots.txt, rate limits, and each platform's terms of use.
"""
from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote, quote_plus, urljoin, urlparse

import requests
from requests.exceptions import HTTPError as RequestsHTTPError
from bs4 import BeautifulSoup

from backend.app.services.jobscrapping.normalize import RawJob

logger = logging.getLogger(__name__)

_PREFIX = "[ingest:third-party]"

_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _indeed_rss_headers() -> dict[str, str]:
    """Indeed often returns 403 to minimal clients; mimic a browser RSS request."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.indeed.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Upgrade-Insecure-Requests": "1",
    }


def _norm_company(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def public_job_matches_company(
    job_company: str,
    target_name: str,
    aliases: list[str] | None = None,
) -> bool:
    """Whether a feed job's employer string matches a tracked company (substring / alias)."""
    jc = _norm_company(job_company)
    if len(jc) < 2:
        return False
    candidates = [_norm_company(target_name)] + [_norm_company(a) for a in (aliases or []) if a]
    candidates = [c for c in candidates if len(c) >= 2]
    for c in candidates:
        if c in jc or jc in c:
            return True
    for part in _norm_company(target_name).replace("&", " ").split():
        if len(part) > 3 and part in jc:
            return True
    return False


def bucket_public_jobs_by_company(
    raw_jobs: list[RawJob],
    tracked_rows: list[dict[str, Any]],
) -> dict[str, list[RawJob]]:
    """Assign each public-feed job to at most one tracked company name."""
    out: dict[str, list[RawJob]] = {}
    enabled = [r for r in tracked_rows if isinstance(r, dict) and r.get("enabled", True) is not False]
    for rj in raw_jobs:
        name = (rj.company or "").strip()
        for row in enabled:
            tname = (row.get("name") or "").strip()
            if not tname:
                continue
            aliases = row.get("company_name_aliases")
            if isinstance(aliases, str):
                aliases = [aliases]
            elif not isinstance(aliases, list):
                aliases = None
            if public_job_matches_company(name, tname, aliases):
                out.setdefault(tname, []).append(rj)
                break
    return out


def fetch_indeed_rss_raw_jobs(
    company: str,
    *,
    timeout_sec: float = 25,
) -> tuple[list[RawJob], list[dict[str, Any]]]:
    """
    Indeed RSS for a free-text query (company name).

    Indeed frequently blocks datacenter IPs and scripts with **403**, or returns **404** when the
    feed is unavailable for a query — that is normal for unofficial RSS use. Those cases return
    empty jobs and **no failure row** (so unified ingest ``errors`` is not inflated). For reliable
    Indeed data use the `Indeed Publisher <https://www.indeed.com/publisher>`_ / partner APIs.
    """
    q = (company or "").strip()
    if len(q) < 2:
        return [], []
    # Try a few URL shapes; some regions/queries behave differently.
    encodings = list(dict.fromkeys([quote_plus(q), quote(q, safe="")]))
    urls = [f"https://www.indeed.com/rss?q={enc}" for enc in encodings]
    headers = _indeed_rss_headers()
    out: list[RawJob] = []
    last_exc: Exception | None = None
    saw_block = False
    for url in dict.fromkeys(urls):
        try:
            r = requests.get(
                url,
                timeout=timeout_sec,
                headers=headers,
                allow_redirects=True,
            )
            if r.status_code in (403, 404):
                saw_block = True
                continue
            r.raise_for_status()
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            if channel is None:
                continue
            for item in channel.findall("item"):
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                title = (title_el.text or "").strip() if title_el is not None else ""
                link = (link_el.text or "").strip() if link_el is not None else ""
                if not title or not link or not link.startswith("http"):
                    continue
                desc = (desc_el.text or "").strip() if desc_el is not None else None
                remote = "remote" in title.lower() or (desc and "remote" in desc.lower())
                out.append(
                    RawJob(
                        title=title[:500],
                        company=q[:200],
                        url=link,
                        location=None,
                        description=(desc or "")[:4000] or None,
                        remote=remote,
                        extra={"adapter": "indeed_rss", "query": q},
                    )
                )
            if out:
                logger.info("%s indeed_rss | company=%s | jobs=%d", _PREFIX, company, len(out))
                return out, []
        except RequestsHTTPError as e:
            resp = getattr(e.response, "status_code", None)
            if resp in (403, 404):
                saw_block = True
                continue
            last_exc = e
        except ET.ParseError as e:
            last_exc = e
        except Exception as e:
            last_exc = e
    if saw_block and last_exc is None:
        logger.info(
            "%s indeed_rss all endpoints blocked or 404 | company=%s (use Indeed Publisher API for production)",
            _PREFIX,
            company,
        )
        return [], []
    if last_exc is not None:
        logger.warning("%s indeed_rss failed | company=%s | %s", _PREFIX, company, last_exc)
        return [], [{"kind": "indeed_rss", "target": company, "message": str(last_exc)}]
    return [], []


def fetch_linkedin_guest_raw_jobs(
    company: str,
    *,
    timeout_sec: float = 25,
) -> tuple[list[RawJob], list[dict[str, Any]]]:
    """
    LinkedIn jobs-guest HTML API (unofficial, brittle). For production, prefer official/partner APIs.
    """
    q = (company or "").strip()
    if len(q) < 2:
        return [], []
    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
        f"keywords={quote(q)}&f_TPR=r604800&position=1&pageNum=0&start=0"
    )
    out: list[RawJob] = []
    seen: set[str] = set()
    try:
        r = requests.get(url, timeout=timeout_sec, headers=_HTTP_HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select('a[href*="/jobs/view/"]'):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            if href.startswith("/"):
                href = urljoin("https://www.linkedin.com", href)
            if href in seen:
                continue
            title = a.get_text(" ", strip=True)
            if len(title) < 3:
                continue
            seen.add(href)
            out.append(
                RawJob(
                    title=title[:500],
                    company=q[:200],
                    url=href.split("?")[0],
                    location=None,
                    description=None,
                    remote="remote" in title.lower(),
                    extra={"adapter": "linkedin_guest_html", "query": q},
                )
            )
            if len(out) >= 50:
                break
        logger.info("%s linkedin_guest | company=%s | jobs=%d", _PREFIX, company, len(out))
        return out, []
    except Exception as e:
        logger.warning("%s linkedin_guest failed | company=%s | %s", _PREFIX, company, e)
        return [], [{"kind": "linkedin", "target": company, "message": str(e)}]


def fetch_naukri_search_raw_jobs(
    company: str,
    *,
    timeout_sec: float = 25,
) -> tuple[list[RawJob], list[dict[str, Any]]]:
    """Naukri keyword search page — best-effort link extraction."""
    q = (company or "").strip()
    if len(q) < 2:
        return [], []
    url = f"https://www.naukri.com/jobs-in-india?k={quote(q)}"
    out: list[RawJob] = []
    seen: set[str] = set()
    try:
        r = requests.get(url, timeout=timeout_sec, headers=_HTTP_HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        base = f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "/job-listings/" not in href and "job-listing" not in href.lower():
                continue
            if href.startswith("/"):
                href = urljoin(base, href)
            if not href.startswith("http") or href in seen:
                continue
            title = a.get_text(" ", strip=True)
            if len(title) < 3:
                continue
            seen.add(href)
            out.append(
                RawJob(
                    title=title[:500],
                    company=q[:200],
                    url=href.split("?")[0],
                    location=None,
                    description=None,
                    remote="remote" in title.lower() or "work from home" in title.lower(),
                    extra={"adapter": "naukri_search_html", "query": q},
                )
            )
            if len(out) >= 50:
                break
        logger.info("%s naukri_search | company=%s | jobs=%d", _PREFIX, company, len(out))
        return out, []
    except Exception as e:
        logger.warning("%s naukri_search failed | company=%s | %s", _PREFIX, company, e)
        return [], [{"kind": "naukri", "target": company, "message": str(e)}]
