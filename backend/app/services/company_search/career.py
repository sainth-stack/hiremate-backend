from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from backend.app.services.company_search.base import BaseATSScraper, JobResult
from backend.app.services.company_search.greenhouse import GreenhouseScraper
from backend.app.services.company_search.lever import LeverScraper
from backend.app.services.company_search.workday import WorkdayScraper

logger = logging.getLogger(__name__)


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _coerce_datetime_value(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return _to_naive_utc(val)
    if isinstance(val, (int, float)):
        ts = float(val)
        if ts > 1e12:
            ts = ts / 1000.0
        try:
            return datetime.utcfromtimestamp(ts)
        except (ValueError, OSError):
            return None
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            if s.endswith("Z") and "+00:00" not in s:
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            return _to_naive_utc(dt)
        except ValueError:
            return None
    return None


def _parse_posted_at_from_dict(obj: dict[str, Any]) -> datetime | None:
    for k in (
        "postedAt",
        "postedDate",
        "datePosted",
        "firstPublishedAt",
        "publishedAt",
        "createdAt",
        "openingDate",
        "listedAt",
        "updatedAt",
    ):
        dt = _coerce_datetime_value(obj.get(k))
        if dt:
            return dt
    return None


_JOB_TITLE_HINT_RE = re.compile(
    r"\b(?:"
    r"engineer(?:ing)?|developer|devops|sre|scientist|researcher|analyst|architect|designer|"
    r"manager|management|director|(?:tech(?:nical)?|team)\s+lead|head\s+of|"
    r"specialist|intern(?:ship)?|coordinator|associate|executive|assistant|"
    r"representative|recruiter|writer|support|consultant|counsel|attorney|"
    r"product\s+manager|program\s+manager|project\s+manager|account\s+manager|"
    r"technical|technician|qa|qae|\bqa\b|sdet|test(?:er|ing)?|automation|"
    r"machine\s+learning|\bml\b|"
    r"security|administrator|"
    r"dba|sales\s+engineer|solutions\s+engineer|graphic|ux|ui|"
    r"frontend|backend|full[\s-]?stack|mobile|ios|android|"
    r"infrastructure|platform|site\s+reliability|kubernetes|"
    r"business\s+systems|revops|operator|nurse|physician|therapist"
    r")\b",
    re.I,
)

# Region / org-chart labels often mistaken for roles in SPA JSON (e.g. Stripe).
_HUB_TITLE_EXACT = frozenset({
    "north america",
    "latin america",
    "south america",
    "middle east",
    "asia pacific",
    "apac",
    "emea",
    "europe",
    "africa",
    "india",
    "united states",
    "canada",
    "uk",
    "ireland",
    "products",
    "product",
    "people",
    "security",
    "bridge",
    "university",
    "tech programs",
    "risk & financial crimes",
    "risk and financial crimes",
    "go to market",
    "gtm",
    "sales",
    "marketing",
    "operations",
    "finance",
    "legal",
    "support",
    "corporate",
})


def listing_title_looks_like_job_posting(title: str) -> bool:
    """Reject nav hubs / regions; keep real role-like titles."""
    t = (title or "").strip()
    if len(t) < 3:
        return False
    tl = t.lower()
    if tl in _HUB_TITLE_EXACT:
        return False
    if _JOB_TITLE_HINT_RE.search(t):
        return True
    if len(t) >= 36:
        return True
    return False


def embedded_record_looks_like_job_posting(obj: dict[str, Any], title: str) -> bool:
    if listing_title_looks_like_job_posting(title):
        return True
    for k in ("description", "jobDescription", "content", "htmlDescription", "jobPostingDescription"):
        v = obj.get(k)
        if isinstance(v, str) and len(v.strip()) > 140:
            return True
    return False


# Playwright: extract job links with clean titles (posting selectors + innerText first line),
# normalize URLs (drop pagination query params), smarter location lines.
CAREER_PLAYWRIGHT_JOB_LINKS_JS = r"""
(args) => {
  const base = args.base;
  const navSkip = new Set((args.navSkip || []).map(s => s.toLowerCase()));
  const entries = [];
  const seen = new Set();
  const dropQ = new Set(["page", "p", "offset", "skip", "cursor", "after", "pagenum", "_p"]);
  function normHref(href) {
    try {
      const u = new URL(href);
      const sp = new URLSearchParams(u.search);
      for (const k of [...sp.keys()]) {
        if (dropQ.has(k.toLowerCase())) sp.delete(k);
      }
      u.search = sp.toString() ? "?" + sp.toString() : "";
      return u.href;
    } catch (e) {
      return href;
    }
  }
  function titleFromAnchor(a) {
    const sels = [
      ".posting-title", ".posting-btn__title", ".posting--title", '[class*="PostingTitle"]',
      '[class*="posting-title"]', '[class*="job-title"]', '[class*="JobCard"] h3', '[class*="JobCard"] h2',
      '[data-testid*="job-title"]', '[class*="ashby-job-posting-brief-title"]', "h3", "h4"
    ];
    for (const s of sels) {
      try {
        const el = a.querySelector(s);
        if (el) {
          const t = (el.textContent || "").trim().replace(/\s+/g, " ");
          if (t.length >= 3 && t.length <= 280) return t.slice(0, 300);
        }
      } catch (e) {}
    }
    const inner = (a.innerText || a.textContent || "").trim();
    const lines = inner.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    if (lines.length) {
      let t = lines[0];
      if (t.length > 280) t = t.slice(0, 280);
      return t.replace(/\s+/g, " ");
    }
    return (a.textContent || "").trim().replace(/\s+/g, " ").slice(0, 300);
  }
  function locFromAnchor(a) {
    const inner = (a.innerText || "").trim();
    const lines = inner.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    for (let i = 1; i < Math.min(lines.length, 6); i++) {
      const L = lines[i];
      if (L.length < 2 || L.length > 130) continue;
      if (/^[\$€£0-9]|\d+[Kk]\s*[–-]|–.*–|Offers Equity|^GTM\s*•|^Engineering\s*•|^Product\s*•/i.test(L)) continue;
      if (/Remote\s*\$|^\$\d|€\d|£\d|\d+K\s*[–-]/i.test(L)) continue;
      return L.length > 120 ? L.slice(0, 120) : L;
    }
    return "";
  }
  const as = document.querySelectorAll(
    'a[href*="job"], a[href*="careers"], a[href*="position"], a[href*="opening"],' +
    ' a[href*="gh_jid"], a[href*="listing"], a[href*="opportunit"], a[href*="requisition"],' +
    ' a[href*="lever.co"], a[href*="ashbyhq.com"],' +
    ' [class*="job"] a, [class*="position"] a, [class*="opening"] a,' +
    ' [data-testid*="job-card"] a, [data-testid*="JobCard"] a, [class*="JobCard"] a'
  );
  function isJobListingPath(href) {
    if (!href) return false;
    let p = "";
    let host = "";
    try {
      const u = new URL(href);
      if (u.searchParams.get("gh_jid")) return true;
      p = u.pathname.toLowerCase().replace(/\/$/, "");
      host = u.hostname.toLowerCase();
    } catch (e) {
      return false;
    }
    if (p === "/jobs" || p === "/job" || p === "/careers" || p === "/career") return false;
    if (p.endsWith("/search") || p.endsWith("/search/")) return false;
    if (/\/[a-z]{2}(-[a-z]{2})?\/jobs\/search/.test(p)) return false;
    if (p.indexOf("/listing/") >= 0) return true;
    const parts = p.split("/").filter(Boolean);
    if (parts.length >= 3 && (p.indexOf("/job/") >= 0 || p.indexOf("/jobs/") >= 0 || p.indexOf("/position/") >= 0 || p.indexOf("/opening/") >= 0)) return true;
    if (parts.length >= 2 && (p.indexOf("/listing") >= 0 || /\/job\/[^/]+\/[0-9]+/.test(p))) return true;
    if (host.indexOf("ashbyhq.com") >= 0 && parts.length >= 2) {
      const last = parts[parts.length - 1];
      if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(last)) return true;
    }
    if (host.indexOf("lever.co") >= 0 && parts.length >= 2) {
      const last = parts[parts.length - 1];
      if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(last)) return true;
    }
    return false;
  }
  for (const a of as) {
    let href = (a.getAttribute("href") || a.href || "").trim();
    if (!href || href.indexOf("javascript:") === 0) continue;
    if (href.charAt(0) === "/") href = new URL(href, base).href;
    else if (href.indexOf("http") !== 0) href = new URL(href, base).href;
    href = normHref(href);
    const title = titleFromAnchor(a);
    if (title.length < 3 || title.length > 300) continue;
    if (seen.has(href)) continue;
    const skip = ["login", "sign in", "home", "about", "contact", "privacy", "terms", "apply now", "submit"];
    let badSkip = false;
    for (let j = 0; j < skip.length; j++) {
      if (title.toLowerCase().indexOf(skip[j]) >= 0) { badSkip = true; break; }
    }
    if (badSkip) continue;
    if (navSkip.has(title.toLowerCase().trim())) continue;
    if (!isJobListingPath(href)) continue;
    seen.add(href);
    let loc = locFromAnchor(a);
    if (!loc) {
      const card = a.closest('[class*="job"], [class*="position"], [class*="opening"], li, article, tr, td');
      if (card) {
        const t = card.textContent || "";
        const tl = t.toLowerCase();
        const locWords = ["bengaluru", "bangalore", "mumbai", "delhi", "hyderabad", "chennai", "pune", "jaipur", "london", "new york", "san francisco", "poland", "germany", "ireland", "portugal", "india"];
        for (let w = 0; w < locWords.length; w++) {
          if (tl.indexOf(locWords[w]) >= 0) { loc = locWords[w]; break; }
        }
        if (!loc && tl.indexOf("remote") >= 0) loc = "Remote";
      }
    }
    entries.push({ url: href, title: title.slice(0, 300), location: loc || null });
  }
  return entries;
}
"""

_PAGINATION_QUERY_KEYS = frozenset({"page", "p", "offset", "skip", "cursor", "after", "pagenum", "_p"})


def _normalize_job_listing_url(url: str) -> str:
    """Drop pagination-related query params so the same role dedupes across listing pages."""
    try:
        p = urlparse(url)
        q = [
            (k, v)
            for k, v in parse_qsl(p.query, keep_blank_values=True)
            if k.lower() not in _PAGINATION_QUERY_KEYS
        ]
        new_query = urlencode(q)
        return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))
    except Exception:
        return url


def _polish_listing_title(title: str) -> str:
    """Fix glued lines (e.g. Greenhouse cards: 'RoleDeptCity' split heuristically)."""
    t = re.sub(r"\s+", " ", (title or "").strip())
    if len(t) < 4:
        return t
    t = re.sub(r"([a-z0-9])([A-Z][a-z])", r"\1 \2", t)
    return re.sub(r"\s+", " ", t).strip()[:300]


class CareerPageScraper(BaseATSScraper):
    ats_type = "career"
    TRACKING_QUERY_PREFIXES = ("utm_",)
    TRACKING_QUERY_KEYS = {"gh_src", "lever-source", "lang", "locale", "source"}
    CTA_KEYWORDS = (
        "view jobs",
        "search jobs",
        "see open roles",
        "view open roles",
        "open positions",
        "career opportunities",
        "find jobs",
        "browse jobs",
        "all jobs",
        "job search",
        "explore jobs",
        "current openings",
        "vacancies",
        "job openings",
        "listings",
        "search roles",
        "open roles",
    )

    def __init__(self, timeout_seconds: int = 15) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        self._memory_path = Path(__file__).resolve().parents[3] / "data" / "career_memory.json"
        self._company_memory: dict[str, dict[str, Any]] = self._load_memory()
        self._last_search_meta: dict[str, Any] = {}

    @property
    def last_search_meta(self) -> dict[str, Any]:
        return dict(self._last_search_meta)

    def _load_memory(self) -> dict[str, dict[str, Any]]:
        if not self._memory_path.exists():
            return {}
        try:
            raw = json.loads(self._memory_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
        except Exception as exc:
            logger.warning("Career memory load failed path=%s error=%s", self._memory_path, exc)
        return {}

    def _save_memory(self) -> None:
        try:
            self._memory_path.parent.mkdir(parents=True, exist_ok=True)
            self._memory_path.write_text(
                json.dumps(self._company_memory, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Career memory save failed path=%s error=%s", self._memory_path, exc)

    def _company_key(self, company: str) -> str:
        if company.startswith("http://") or company.startswith("https://"):
            return company.lower().strip()
        return self.normalize_company(company)

    def _canonicalize_url(self, url: str) -> str:
        try:
            parsed = urlparse((url or "").strip())
            if not parsed.scheme:
                return url
            clean_fragment = ""
            if parsed.fragment and parsed.fragment.startswith("/"):
                parsed = parsed._replace(path=parsed.fragment, fragment="")
            query_items = []
            for key, value in parse_qsl(parsed.query, keep_blank_values=True):
                key_l = key.lower()
                if key_l in self.TRACKING_QUERY_KEYS:
                    continue
                if any(key_l.startswith(prefix) for prefix in self.TRACKING_QUERY_PREFIXES):
                    continue
                query_items.append((key, value))
            clean_query = urlencode(query_items, doseq=True)
            clean_path = parsed.path.rstrip("/") or "/"
            canonical = urlunparse(
                (
                    parsed.scheme.lower(),
                    parsed.netloc.lower(),
                    clean_path,
                    parsed.params,
                    clean_query,
                    clean_fragment,
                )
            )
            return canonical
        except Exception:
            return url

    def _path_depth(self, url: str) -> int:
        parsed = urlparse(url)
        return len([part for part in parsed.path.split("/") if part])

    def _extract_iframe_candidates(self, base_url: str, soup: BeautifulSoup) -> list[str]:
        urls: list[str] = []
        for iframe in soup.select("iframe[src]"):
            src = iframe.get("src", "").strip()
            if not src:
                continue
            full_url = self._canonicalize_url(urljoin(base_url, src))
            haystack = full_url.lower()
            if not any(
                token in haystack
                for token in (
                    "greenhouse",
                    "lever",
                    "workday",
                    "ashby",
                    "smartrecruiters",
                    "/jobs",
                    "/careers",
                    "jobsearch",
                )
            ):
                continue
            urls.append(full_url)
        return list(dict.fromkeys(urls))

    def _extract_cta_links(self, base_url: str, soup: BeautifulSoup) -> list[str]:
        candidates: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "").strip()
            label = anchor.get_text(" ", strip=True).lower()
            if not href or href.startswith("javascript:"):
                continue
            href_lower = href.lower()
            parsed_href = urlparse(href_lower)
            combined_path = f"{parsed_href.path} {parsed_href.fragment}".lower()
            looks_like_listing = any(
                token in combined_path
                for token in (
                    "/jobs",
                    "/careers",
                    "jobsearch",
                    "/openings",
                    "/positions",
                    "/vacancies",
                    "/vacancy",
                    "job-board",
                    "postings",
                    "requisition",
                    "opportunit",
                    "/listing",
                    "listings",
                    "/search",
                )
            )
            is_detail_page = any(
                token in combined_path
                for token in ("/listing/", "/job/", "/jobs/job/", "/jobs/view/", "/job?id=")
            )
            if any(keyword in label for keyword in self.CTA_KEYWORDS):
                if looks_like_listing and not is_detail_page:
                    candidates.append(self._canonicalize_url(urljoin(base_url, href)))
                continue
            href_l = href.lower()
            if any(token in href_l for token in ("/jobs", "/careers", "jobsearch", "/openings", "/positions")):
                if is_detail_page:
                    continue
                candidates.append(self._canonicalize_url(urljoin(base_url, href)))
        for form in soup.find_all("form"):
            action = (form.get("action") or "").strip()
            if action and any(token in action.lower() for token in ("jobs", "career", "search")):
                candidates.append(self._canonicalize_url(urljoin(base_url, action)))
        return list(dict.fromkeys(candidates))

    def _extract_nested_job_list_urls(self, entry_url: str, soup: BeautifulSoup) -> list[str]:
        """
        Follow one level of same-origin career navigation (landing → “View jobs” → real listing).
        Scraping only the main careers homepage often misses listings embedded on inner routes.
        """
        first = self._extract_cta_links(entry_url, soup)
        parsed_entry = urlparse(entry_url)
        entry_host = parsed_entry.netloc.lower()
        nested: list[str] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        }
        for u in first[:8]:
            pu = urlparse(u)
            if pu.netloc.lower() != entry_host:
                continue
            if u.rstrip("/") == entry_url.rstrip("/"):
                continue
            try:
                r = requests.get(u, headers=headers, timeout=min(12, self.timeout_seconds))
                if r.status_code != 200:
                    continue
                s2 = BeautifulSoup(r.text or "", "html.parser")
                nested.extend(self._extract_cta_links(u, s2))
            except Exception as exc:
                logger.debug("nested career navigation fetch failed url=%s error=%s", u, exc)
        return list(dict.fromkeys(nested))

    def _job_fingerprint(self, jobs: list[JobResult]) -> str:
        if not jobs:
            return ""
        signatures = sorted(
            f"{(job.role or '').strip().lower()}|{(job.location or '').strip().lower()}|{self._canonicalize_url(job.apply_url)}"
            for job in jobs
        )
        joined = "\n".join(signatures)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def _memory_get(self, company: str) -> dict[str, Any] | None:
        key = self._company_key(company)
        data = self._company_memory.get(key)
        if not isinstance(data, dict):
            return None
        return data

    def _memory_set(
        self,
        company: str,
        canonical_jobs_url: str,
        ats_provider: str | None,
        discovery_strategy: str,
    ) -> None:
        key = self._company_key(company)
        self._company_memory[key] = {
            "canonical_jobs_url": canonical_jobs_url,
            "ats_provider": ats_provider,
            "discovery_strategy": discovery_strategy,
        }
        self._save_memory()

    def discover_careers_url(self, company: str) -> Optional[str]:
        """
        Discover careers/jobs URL. Order (fast → slow):

        1. User-provided ``https://`` URL
        2. Common ``careers.{slug}.com`` / ``/careers`` patterns (usually hits first)
        3. Sitemap + homepage links
        4. ``duckduckgo-search`` API (structured results)
        5. Google HTML scraping (often zero matches; kept as fallback)
        6. DuckDuckGo HTML scraping
        """
        if company.startswith("http://") or company.startswith("https://"):
            normalized = self._canonicalize_url(company)
            logger.info("Career page using provided URL url=%s canonical=%s", company, normalized)
            return normalized

        search_query = f"{company} careers page"
        slug = self.normalize_company(company)

        url = self._discover_common_url_patterns(company, slug)
        if url:
            return url

        url = self._discover_sitemap_and_homepage(slug)
        if url:
            return url

        url = self._discover_via_ddgs(company)
        if url:
            return url

        url = self._discover_via_google_html(search_query)
        if url:
            return url

        url = self._discover_via_ddg_html(search_query)
        if url:
            return url

        logger.warning("Career page not found for company=%s tried all strategies", company)
        return None

    def _discover_via_sitemap(self, domain_base: str) -> list[str]:
        """Fetch sitemap.xml / sitemap_index.xml and return URLs containing career/job/position."""
        urls: list[str] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/xml,text/xml,*/*;q=0.9",
        }
        keywords = ("career", "job", "position", "opening", "vacancy", "opportunit")
        sitemap_candidates = [
            f"{domain_base.rstrip('/')}/sitemap.xml",
            f"{domain_base.rstrip('/')}/sitemap_index.xml",
            f"{domain_base.rstrip('/')}/sitemap-index.xml",
        ]
        for sitemap_url in sitemap_candidates:
            try:
                resp = requests.get(sitemap_url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    continue
                text = (resp.text or "").lower()
                # Parse simple sitemap: <loc>URL</loc>
                for match in re.finditer(r"<loc>\s*([^<]+)\s*</loc>", text, re.IGNORECASE):
                    loc = match.group(1).strip()
                    if any(k in loc for k in keywords):
                        urls.append(loc)
                # If this is a sitemap index, follow first few child sitemaps
                if "sitemapindex" in text or "sitemap_index" in sitemap_url:
                    for child_match in re.finditer(r"<loc>\s*([^<]+)\s*</loc>", text, re.IGNORECASE):
                        child_url = child_match.group(1).strip()
                        if any(k in child_url for k in keywords) or "sitemap" in child_url:
                            try:
                                cr = requests.get(child_url, headers=headers, timeout=8)
                                if cr.status_code == 200:
                                    ct = (cr.text or "").lower()
                                    for m in re.finditer(r"<loc>\s*([^<]+)\s*</loc>", ct, re.IGNORECASE):
                                        u = m.group(1).strip()
                                        if any(k in u for k in keywords):
                                            urls.append(u)
                            except Exception:
                                pass
                if urls:
                    logger.info("Sitemap discovery found %d career URLs from %s", len(urls), sitemap_url)
                    return list(dict.fromkeys(urls))
            except Exception as e:
                logger.debug("Sitemap fetch failed url=%s error=%s", sitemap_url, str(e))
        return list(dict.fromkeys(urls))

    def _discover_via_homepage_links(self, domain_base: str) -> list[str]:
        """Crawl homepage and collect links whose text/href contain careers, jobs, open positions."""
        homepage = domain_base.rstrip("/") + "/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        }
        candidates: list[str] = []
        try:
            resp = requests.get(homepage, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text or "", "html.parser")
            for a in soup.find_all("a", href=True):
                href = (a.get("href") or "").strip()
                text = a.get_text(" ", strip=True).lower()
                if not href or href.startswith("#") or href.startswith("javascript:"):
                    continue
                full_url = urljoin(homepage, href)
                url_lower = full_url.lower()
                text_keywords = ("careers", "jobs", "open positions", "work with us", "join us", "opportunities", "hiring")
                path_keywords = ("/careers", "/jobs", "/career", "/job", "/work-with-us", "/join-us", "/openings", "/positions")
                if any(k in text for k in text_keywords) or any(k in url_lower for k in path_keywords):
                    if self._looks_like_careers_url(full_url):
                        candidates.append(self._canonicalize_url(full_url))
            logger.info("Homepage discovery found %d career link candidates from %s", len(candidates), homepage)
            return list(dict.fromkeys(candidates))
        except Exception as e:
            logger.debug("Homepage links fetch failed url=%s error=%s", homepage, str(e))
            return []

    def _extract_jobs_from_url(
        self,
        url: str,
        company: str,
        role: str,
        skills: list[str],
        use_playwright: bool = False,
    ) -> tuple[list[JobResult], dict[str, Any]]:
        canonical_url = self._canonicalize_url(url)
        try:
            resp = requests.get(
                canonical_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
                timeout=self.timeout_seconds,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            logger.warning("Career page request failed url=%s error=%s", canonical_url, exc)
            return [], {"url": canonical_url, "status": "request_failed"}

        if resp.status_code != 200:
            logger.info("Career page fetch non-200 status=%s url=%s", resp.status_code, canonical_url)
            return [], {"url": canonical_url, "status": f"http_{resp.status_code}"}

        final_url = self._canonicalize_url(resp.url or canonical_url)
        content_type = (resp.headers.get("Content-Type") or "").lower()
        logger.info("Career page content fetched url=%s content_type=%s", final_url, content_type)

        if "application/json" in content_type:
            try:
                jobs = self._extract_jobs_from_json_payload(resp.json(), final_url, company)
                return self.dedupe_jobs(jobs), {
                    "url": final_url,
                    "status": "json",
                    "ats_provider": None,
                    "job_count": len(jobs),
                }
            except Exception as exc:
                logger.debug("Career page JSON parse failed url=%s error=%s", final_url, exc)

        html_text = resp.text or ""
        soup = BeautifulSoup(html_text, "html.parser")
        inspection = self._inspect_career_page(final_url, soup, html_text)

        iframe_candidates = self._extract_iframe_candidates(final_url, soup)
        for iframe_url in iframe_candidates:
            iframe_provider = self._detect_ats_provider(iframe_url, "", [])
            if iframe_provider:
                logger.info(
                    "Career page iframe ATS detected provider=%s parent=%s iframe=%s",
                    iframe_provider,
                    final_url,
                    iframe_url,
                )
                iframe_jobs = self._fetch_jobs_via_ats_adapter(
                    iframe_provider, iframe_url, company, role, skills
                )
                if iframe_jobs:
                    return self.dedupe_jobs(iframe_jobs), {
                        "url": iframe_url,
                        "status": "iframe_ats",
                        "ats_provider": iframe_provider,
                        "job_count": len(iframe_jobs),
                    }

        ats_provider = inspection.get("ats_provider")
        if ats_provider:
            ats_results = self._fetch_jobs_via_ats_adapter(
                ats_provider, final_url, company, role, skills
            )
            if ats_results:
                return self.dedupe_jobs(ats_results), {
                    "url": final_url,
                    "status": "ats",
                    "ats_provider": ats_provider,
                    "job_count": len(ats_results),
                }

        # Only Playwright-based extraction for HTML career pages (no static/BeautifulSoup extraction)
        if use_playwright:
            playwright_results = self._extract_jobs_with_playwright(final_url, company)
            if playwright_results:
                deduped = self.dedupe_jobs(playwright_results)
                return deduped, {
                    "url": final_url,
                    "status": "playwright",
                    "ats_provider": ats_provider,
                    "job_count": len(deduped),
                }

        return [], {"url": final_url, "status": "no_jobs", "ats_provider": ats_provider, "job_count": 0}

    def _score_candidate(
        self,
        url: str,
        jobs: list[JobResult],
        extraction_status: str,
        ats_provider: str | None,
    ) -> int:
        job_count = len(jobs)
        ats_bonus = 20 if ats_provider else 0
        api_bonus = 12 if extraction_status in {"api", "discovered_api", "json"} else 0
        pagination_bonus = 6 if any(token in url.lower() for token in ("page=", "offset", "cursor", "search")) else 0
        nav_penalty = 10 if extraction_status in {"no_jobs", "request_failed"} else 0
        return (job_count * 10) + ats_bonus + api_bonus + pagination_bonus - nav_penalty

    def _select_canonical_jobs_url(
        self,
        entry_url: str,
        company: str,
        role: str,
        skills: list[str],
    ) -> tuple[str, list[JobResult], dict[str, Any]]:
        canonical_entry = self._canonicalize_url(entry_url)
        candidates = [canonical_entry]
        try:
            resp = requests.get(canonical_entry, timeout=self.timeout_seconds)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text or "", "html.parser")
                candidates.extend(self._extract_iframe_candidates(canonical_entry, soup))
                candidates.extend(self._extract_cta_links(canonical_entry, soup))
                candidates.extend(self._extract_nested_job_list_urls(canonical_entry, soup))
        except Exception as exc:
            logger.debug("Canonical prefetch failed url=%s error=%s", canonical_entry, exc)

        unique_candidates = list(dict.fromkeys(candidates))[:18]
        logger.info("Career funnel candidates company=%s count=%d", company, len(unique_candidates))
        evaluation_rows: list[dict[str, Any]] = []
        best_url = canonical_entry
        best_jobs: list[JobResult] = []
        best_status = "no_jobs"
        best_ats: str | None = None
        best_score = -10**9
        best_job_ids: set[str] = set()

        for candidate_url in unique_candidates:
            jobs, details = self._extract_jobs_from_url(
                candidate_url,
                company,
                role,
                skills,
                use_playwright=False,
            )
            status = str(details.get("status") or "no_jobs")
            ats_provider = details.get("ats_provider")
            resolved_url = self._canonicalize_url(str(details.get("url") or candidate_url))
            job_ids = {job.external_id for job in jobs}
            score = self._score_candidate(resolved_url, jobs, status, ats_provider)
            row = {
                "url": resolved_url,
                "status": status,
                "ats_provider": ats_provider,
                "job_count": len(job_ids),
                "score": score,
                "path_depth": self._path_depth(resolved_url),
                "fingerprint": self._job_fingerprint(jobs),
                "job_ids": job_ids,
            }
            evaluation_rows.append(row)
            logger.info(
                "Career funnel evaluate url=%s status=%s jobs=%d score=%d ats=%s",
                resolved_url,
                status,
                len(job_ids),
                score,
                ats_provider or "-",
            )
            if score > best_score or (
                score == best_score and self._path_depth(resolved_url) > self._path_depth(best_url)
            ):
                best_score = score
                best_url = resolved_url
                best_jobs = jobs
                best_status = status
                best_ats = ats_provider if isinstance(ats_provider, str) else None
                best_job_ids = job_ids

        navigation_only_urls: list[str] = []
        for row in evaluation_rows:
            if row["url"] == best_url:
                continue
            row_ids = row["job_ids"]
            if not row_ids or not best_job_ids:
                continue
            overlap = len(row_ids.intersection(best_job_ids)) / max(len(row_ids), 1)
            if overlap >= 0.8 and row["path_depth"] <= self._path_depth(best_url):
                navigation_only_urls.append(row["url"])

        meta = {
            "canonical_jobs_url": best_url,
            "entry_url": canonical_entry,
            "candidate_urls": [row["url"] for row in evaluation_rows],
            "navigation_only_urls": navigation_only_urls,
            "extraction_status": best_status,
            "ats_provider": best_ats,
            "jobs_found": len(best_jobs),
        }
        return best_url, best_jobs, meta

    def search_jobs(self, company: str, role: str, skills: list[str], location: str = "") -> list[JobResult]:
        self._last_search_meta = {}
        memory = self._memory_get(company) or {}
        discovery_strategy = "discovery"
        entry_url = memory.get("canonical_jobs_url")
        if entry_url:
            logger.info("Career memory hit company=%s canonical=%s", company, entry_url)
            discovery_strategy = "memory"
        else:
            entry_url = self.discover_careers_url(company)
        if not entry_url:
            logger.warning("Career page not found company=%s", company)
            self._last_search_meta = {
                "company": company,
                "discovery_strategy": discovery_strategy,
                "canonical_jobs_url": None,
                "candidate_urls": [],
                "navigation_only_urls": [],
                "ats_provider": None,
                "jobs_found": 0,
            }
            return []

        canonical_url, jobs, funnel_meta = self._select_canonical_jobs_url(
            entry_url, company, role, skills
        )
        if not jobs:
            jobs, details = self._extract_jobs_from_url(
                canonical_url,
                company,
                role,
                skills,
                use_playwright=True,
            )
            funnel_meta["extraction_status"] = details.get("status")
            funnel_meta["jobs_found"] = len(jobs)
            if details.get("ats_provider"):
                funnel_meta["ats_provider"] = details.get("ats_provider")
        logger.info(
            "Career funnel selected company=%s canonical=%s jobs=%d strategy=%s",
            company,
            canonical_url,
            len(jobs),
            discovery_strategy,
        )
        self._memory_set(
            company=company,
            canonical_jobs_url=canonical_url,
            ats_provider=funnel_meta.get("ats_provider"),
            discovery_strategy=discovery_strategy,
        )
        self._last_search_meta = {
            "company": company,
            "discovery_strategy": discovery_strategy,
            **funnel_meta,
        }
        out = self.dedupe_jobs(jobs)
        role_q = (role or "").strip()
        if role_q:
            out = [j for j in out if self.role_matches(j.role, role_q)]
        loc = (location or "").strip()
        if loc:
            out = [j for j in out if self.location_matches(j.location, loc)]
        return out

    def _discover_common_url_patterns(self, company: str, slug: str) -> Optional[str]:
        """Fast path: try obvious ``careers.`` / ``/careers`` URLs before slow search HTML."""
        common_patterns = [
            f"https://careers.{slug}.com",
            f"https://jobs.{slug}.com",
            f"https://www.careers.{slug}.com",
            f"https://{slug}.com/careers",
            f"https://{slug}.com/jobs",
            f"https://www.{slug}.com/careers",
            f"https://www.{slug}.com/jobs",
            f"https://{slug}.com/career",
            f"https://{slug}.com/job-openings",
            f"https://{slug}.com/work-with-us",
            f"https://{slug}.com/join-us",
            f"https://www.{slug}.com/work-with-us",
            f"https://www.{slug}.com/join-us",
            f"https://{slug}.com/about/careers",
            f"https://www.{slug}.com/about/careers",
            f"https://{slug}.com/company/careers",
            f"https://www.{slug}.com/company/careers",
        ]
        logger.info(
            "Career page trying %d common patterns first company=%s slug=%s",
            len(common_patterns),
            company,
            slug,
        )
        for url in common_patterns:
            try:
                if self._url_ok(url):
                    logger.info("Career page FOUND via pattern url=%s", url)
                    actual_jobs_url = self._find_job_listing_page(url)
                    return self._canonicalize_url(actual_jobs_url or url)
            except Exception as e:
                logger.debug("Career page pattern exception url=%s error=%s", url, str(e))
                continue
        return None

    def _discover_sitemap_and_homepage(self, slug: str) -> Optional[str]:
        for domain_base in [f"https://{slug}.com", f"https://www.{slug}.com"]:
            sitemap_urls = self._discover_via_sitemap(domain_base)
            for url in sitemap_urls[:5]:
                try:
                    if self._url_ok(url):
                        logger.info("Career page FOUND via sitemap url=%s", url)
                        actual_jobs_url = self._find_job_listing_page(url)
                        return self._canonicalize_url(actual_jobs_url or url)
                except Exception:
                    continue
        for domain_base in [f"https://{slug}.com", f"https://www.{slug}.com"]:
            homepage_urls = self._discover_via_homepage_links(domain_base)
            for url in homepage_urls[:5]:
                try:
                    if self._url_ok(url):
                        logger.info("Career page FOUND via homepage link url=%s", url)
                        actual_jobs_url = self._find_job_listing_page(url)
                        return self._canonicalize_url(actual_jobs_url or url)
                except Exception:
                    continue
        return None

    def _discover_via_ddgs(self, company: str) -> Optional[str]:
        """Official duckduckgo-search package (more reliable than scraping DDG HTML)."""
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return None
        query = f"{company} careers jobs"
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=8))
        except Exception as exc:
            logger.debug("DDGS package search failed company=%s error=%s", company, exc)
            return None
        for r in results:
            if not isinstance(r, dict):
                continue
            href = (r.get("href") or r.get("url") or "").strip()
            if not href.startswith("http"):
                continue
            if not self._looks_like_careers_url(href):
                continue
            try:
                if self._url_ok(href):
                    logger.info("Career page discovered via DDGS package url=%s", href)
                    actual_jobs_url = self._find_job_listing_page(href)
                    return self._canonicalize_url(actual_jobs_url or href)
            except Exception:
                continue
        return None

    def _discover_via_google_html(self, search_query: str) -> Optional[str]:
        google_search_url = f"https://www.google.com/search?q={requests.utils.quote(search_query)}"
        logger.info("Career page searching Google HTML query='%s'", search_query)
        try:
            resp = requests.get(
                google_search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                timeout=self.timeout_seconds,
            )
            logger.info("Google search response status=%d", resp.status_code)
            if resp.status_code != 200:
                logger.warning("Google search returned non-200 status=%d", resp.status_code)
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            found_urls = []
            for link in soup.select("a"):
                href = link.get("href", "")
                if not href:
                    continue
                if "/url?q=" in href:
                    try:
                        actual_url = href.split("/url?q=")[1].split("&")[0]
                        actual_url = requests.utils.unquote(actual_url)
                        if self._looks_like_careers_url(actual_url):
                            found_urls.append(actual_url)
                            logger.info("Career page candidate from Google url=%s", actual_url)
                    except Exception:
                        continue
                elif href.startswith("http") and self._looks_like_careers_url(href):
                    found_urls.append(href)
                    logger.info("Career page candidate from Google direct url=%s", href)
            logger.info("Google search extracted %d career page candidates", len(found_urls))
            if not found_urls:
                logger.warning("Google search returned 0 career page candidates")
                return None
            for idx, url in enumerate(found_urls[:5], 1):
                try:
                    logger.info("Google result %d/%d: checking url=%s", idx, min(len(found_urls), 5), url)
                    if self._url_ok(url):
                        logger.info("Career page discovered via Google url=%s", url)
                        actual_jobs_url = self._find_job_listing_page(url)
                        return self._canonicalize_url(actual_jobs_url or url)
                except Exception:
                    continue
        except Exception as e:
            logger.warning("Google search exception error=%s", str(e))
        return None

    def _discover_via_ddg_html(self, search_query: str) -> Optional[str]:
        ddg_search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(search_query)}"
        logger.info("Career page trying DuckDuckGo HTML search")
        try:
            resp = requests.get(
                ddg_search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
                timeout=self.timeout_seconds,
            )
            logger.info("DuckDuckGo search response status=%d", resp.status_code)
            if resp.status_code != 200:
                logger.warning("DuckDuckGo search returned non-200 status=%d", resp.status_code)
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            found_urls = []
            for anchor in soup.select("a"):
                href = anchor.get("href", "")
                if href and href.startswith("http") and self._looks_like_careers_url(href):
                    found_urls.append(href)
                    logger.info("Career page candidate from DuckDuckGo url=%s", href)
            logger.info("DuckDuckGo HTML extracted %d career page candidates", len(found_urls))
            if not found_urls:
                logger.warning("DuckDuckGo HTML returned 0 career page candidates")
                return None
            for idx, url in enumerate(found_urls[:5], 1):
                try:
                    logger.info("DuckDuckGo result %d/%d: checking url=%s", idx, min(len(found_urls), 5), url)
                    if self._url_ok(url):
                        logger.info("Career page discovered via DuckDuckGo HTML url=%s", url)
                        actual_jobs_url = self._find_job_listing_page(url)
                        return self._canonicalize_url(actual_jobs_url or url)
                except Exception:
                    continue
        except Exception as e:
            logger.warning("DuckDuckGo HTML exception error=%s", str(e))
        return None

    def _inspect_career_page(self, base_url: str, soup: BeautifulSoup, html_text: str) -> dict:
        text = html_text or ""
        body_text = soup.get_text(" ", strip=True)
        has_job_cards = bool(
            soup.select(
                ".job, .job-card, .opening, .position, .opening, li.job, a[href*='job'], a[href*='career']"
            )
        )
        has_next_data = bool(soup.find("script", id="__NEXT_DATA__"))
        has_embedded_json = bool(soup.find("script", type="application/json")) or has_next_data
        has_state_script = any(
            token in text for token in ["__NEXT_DATA__", "__INITIAL_STATE__", "__APOLLO_STATE__"]
        )
        is_empty = len(body_text) < 40
        is_js_root = bool(soup.select("app-root, #root, #__next, #app"))
        lower_body = body_text.lower()
        has_loading = "loading" in lower_body or "please wait" in lower_body
        has_js_notice = "enable javascript" in lower_body or "requires javascript" in lower_body
        is_js_rendered = is_empty or is_js_root or has_loading or has_js_notice
        script_srcs = [urljoin(base_url, s.get("src")) for s in soup.select("script[src]")]
        ats_provider = self._detect_ats_provider(base_url, text, script_srcs)
        return {
            "has_job_cards": has_job_cards,
            "has_next_data": has_next_data or has_state_script,
            "has_embedded_json": has_embedded_json or has_state_script,
            "is_js_rendered": is_js_rendered,
            "script_srcs": script_srcs,
            "ats_provider": ats_provider,
        }

    def _detect_ats_provider(self, base_url: str, html_text: str, script_srcs: list[str]) -> str | None:
        text = (html_text or "").lower()
        haystack = " ".join([base_url.lower(), text] + [src.lower() for src in script_srcs])
        patterns = {
            "greenhouse": ["greenhouse.io", "boards.greenhouse.io"],
            "lever": ["lever.co", "jobs.lever.co"],
            "workday": ["myworkdayjobs.com", "/workday", "/wd/"],
            "smartrecruiters": ["smartrecruiters.com"],
            "ashby": ["ashbyhq.com"],
            "mynexthire": ["mynexthire.com"],
            "taleo": ["taleo.net"],
        }
        for provider, signals in patterns.items():
            if any(signal in haystack for signal in signals):
                return provider
        return None

    def _fetch_jobs_via_ats_adapter(
        self,
        ats_provider: str,
        careers_url: str,
        company: str,
        role: str,
        skills: list[str],
    ) -> list[JobResult]:
        if ats_provider == "greenhouse":
            slug = self._extract_slug_from_url(careers_url)
            return GreenhouseScraper().search_jobs(slug or company, role, skills)
        if ats_provider == "lever":
            slug = self._extract_slug_from_url(careers_url)
            return LeverScraper().search_jobs(slug or company, role, skills)
        if ats_provider == "workday":
            slug = self._extract_workday_slug(careers_url) or company
            return WorkdayScraper().search_jobs(slug, role, skills)
        if ats_provider == "smartrecruiters":
            return self._fetch_smartrecruiters_jobs(careers_url, company)
        if ats_provider == "ashby":
            return self._fetch_ashby_jobs(careers_url, company)
        if ats_provider == "mynexthire":
            return self._fetch_mynexthire_jobs(careers_url, company)
        if ats_provider == "taleo":
            return self._fetch_taleo_jobs(careers_url, company)
        return []

    def _extract_slug_from_url(self, careers_url: str) -> str | None:
        parsed = urlparse(careers_url)
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            return parts[0]
        return None

    def _extract_workday_slug(self, careers_url: str) -> str | None:
        parsed = urlparse(careers_url)
        host_parts = parsed.netloc.split(".")
        if host_parts:
            return host_parts[0]
        return None

    def _fetch_smartrecruiters_jobs(self, careers_url: str, company: str) -> list[JobResult]:
        slug = self._extract_slug_from_url(careers_url) or company
        api_url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
        return self._fetch_jobs_from_api_url(api_url, careers_url, company)

    def _fetch_ashby_jobs(self, careers_url: str, company: str) -> list[JobResult]:
        slug = self._extract_slug_from_url(careers_url) or company
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        return self._fetch_jobs_from_api_url(api_url, careers_url, company)

    def _fetch_mynexthire_jobs(
        self,
        careers_url: str,
        company: str,
        api_url: str | None = None,
    ) -> list[JobResult]:
        parsed = urlparse(api_url or careers_url)
        host = parsed.netloc or ""
        slug = host.split(".mynexthire.com")[0] if "mynexthire.com" in host else None
        slug = slug or self.normalize_company(company)
        api_url = api_url or f"https://{slug}.mynexthire.com/employer/careers/reqlist/get"
        payload = {"employerShortName": slug, "source": "careers"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=self.timeout_seconds)
            if resp.status_code != 200:
                return []
            data = resp.json()
        except Exception:
            return []
        jobs = data.get("reqDetailsBOList") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            return []
        results: list[JobResult] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            title = job.get("reqTitle") or job.get("roleName")
            req_id = job.get("reqId")
            location = job.get("location") or job.get("locationAddress")
            if not title:
                continue
            apply_url = careers_url
            external_id = hashlib.sha256(f"{careers_url}:{req_id or title}".encode("utf-8")).hexdigest()
            results.append(
                JobResult(
                    company=company,
                    role=str(title),
                    location=str(location) if location else None,
                    apply_url=apply_url,
                    ats_type=self.ats_type,
                    external_id=external_id,
                    description=job.get("jdDisplay"),
                )
            )
        return results

    def _fetch_taleo_jobs(self, careers_url: str, company: str) -> list[JobResult]:
        parsed = urlparse(careers_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        candidates = [
            careers_url,
            f"{base}/careersection/{self.normalize_company(company)}/jobsearch.ftl?lang=en",
            f"{base}/careersection/{self.normalize_company(company)}/jobsearch.ftl",
        ]
        for url in candidates:
            results = self._fetch_jobs_from_api_url(url, careers_url, company)
            if results:
                return results
        return []

    def _fetch_jobs_from_api_url(
        self,
        api_url: str,
        base_url: str,
        company: str,
    ) -> list[JobResult]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json,text/html,*/*",
            "Content-Type": "application/json",
        }
        
        # Handle known ATS patterns
        if "mynexthire.com/employer/careers/reqlist/get" in api_url:
            logger.info("Career page using Mynexthire API url=%s", api_url)
            return self._fetch_mynexthire_jobs(base_url, company, api_url=api_url)
        
        try:
            # Try GET first (simple)
            resp = requests.get(api_url, headers=headers, timeout=self.timeout_seconds)
            if resp.status_code in (200, 201):
                content_type = (resp.headers.get("Content-Type") or "").lower()
                if "application/json" in content_type:
                    data = resp.json()
                    results = self._extract_jobs_from_json_payload(data, base_url, company)
                    if results:
                        return results
                # Try parsing as HTML only if it looks like HTML
                elif "text/html" in content_type and len(resp.content) < 500000:
                    return self._extract_jobs_generic(BeautifulSoup(resp.text, "html.parser"), base_url, company)
        except Exception as e:
            logger.debug("GET failed for url=%s error=%s", api_url, str(e))
        
        # Try GET with query parameters only for Amazon-style search endpoints
        if "/search.json" in api_url or "/en/jobs.json" in api_url:
            query_params_sets = [
                {"offset": 0, "result_limit": 100, "sort": "recent"},
            ]
            
            for params in query_params_sets:
                try:
                    resp = requests.get(api_url, params=params, headers=headers, timeout=8)
                    if resp.status_code in (200, 201):
                        content_type = (resp.headers.get("Content-Type") or "").lower()
                        if "application/json" in content_type:
                            data = resp.json()
                            results = self._extract_jobs_from_json_payload(data, base_url, company)
                            if results:
                                logger.info("GET with params success url=%s jobs=%d", api_url, len(results))
                                return results
                except Exception:
                    continue
        
        # Try POST with common payloads - reduced to most effective ones only
        common_post_payloads = [
            {"jobType": "normal", "size": 100, "page": 1, "search": ""},  # CARS24 format
            {},  # Empty payload
            {"page": 1, "size": 100},
        ]
        
        for idx, payload in enumerate(common_post_payloads, 1):
            try:
                resp = requests.post(
                    api_url,
                    headers=headers,
                    json=payload,
                    timeout=5,  # Shorter timeout
                )
                if resp.status_code in (200, 201):
                    logger.info("POST SUCCESS %s payload_idx=%d status=%d", api_url, idx, resp.status_code)
                    content_type = (resp.headers.get("Content-Type") or "").lower()
                    if "application/json" in content_type:
                        data = resp.json()
                        
                        # Check if this is a metadata/category response
                        if isinstance(data, dict) and self._is_metadata_response(data):
                            logger.debug("POST %s returned metadata, skipping", api_url)
                            continue
                        
                        results = self._extract_jobs_from_json_payload(data, base_url, company)
                        if results:
                            logger.info("Career page POST API success url=%s jobs=%d", api_url, len(results))
                            return results
            except requests.Timeout:
                continue
            except Exception:
                continue
        
        return []
    
    def _is_metadata_response(self, data: dict) -> bool:
        """Check if API response is metadata/categories rather than job listings."""
        metadata_keys = {
            "jobCategories", "categories", "filters", "facets", "teams",
            "departments", "locations", "jobTypes", "metadata", "config",
        }
        return any(key in data for key in metadata_keys)

    def _looks_like_careers_url(self, url: str) -> bool:
        """Check if URL looks like a careers/jobs page."""
        url_lower = url.lower()
        parsed = urlparse(url_lower)

        # Check subdomain (e.g., careers.company.com, jobs.company.com)
        if parsed.netloc:
            subdomain = parsed.netloc.split('.')[0]
            if subdomain in ['careers', 'jobs', 'job', 'career', 'work', 'hiring']:
                return True

        # Check path (e.g., company.com/careers, company.com/jobs)
        path = parsed.path
        career_keywords = [
            '/careers', '/jobs', '/job-openings', '/career', '/job',
            '/work-with-us', '/join-us', '/hiring', '/opportunities',
            '/job-opportunities', '/open-positions', '/vacancies'
        ]
        if any(keyword in path for keyword in career_keywords):
            return True

        # Check query params (e.g., careers.company.com/#/careers)
        if parsed.fragment and any(keyword in parsed.fragment for keyword in ['/careers', '/jobs']):
            return True

        return False

    def _looks_like_inner_job_list_url(self, url: str) -> bool:
        """Paths that usually point to a searchable listing, not a single job detail page."""
        u = (url or "").lower()
        if any(
            token in u
            for token in (
                "/jobs",
                "jobsearch",
                "/job-search",
                "/search",
                "/openings",
                "/positions",
                "/vacancies",
                "/vacancy",
                "job-board",
                "/postings",
                "/requisitions",
                "/opportunit",
                "/listings",
                "/careers/",
                "/career/",
            )
        ):
            return True
        if "?" in u and any(
            q in u for q in ("job", "search", "keyword", "location", "query", "career")
        ):
            return True
        return False

    def _url_ok(self, url: str) -> bool:
        """Check if URL is accessible and returns 200 OK."""
        normalized = self._canonicalize_url(url)
        try:
            resp = requests.get(
                normalized,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                timeout=10,
                allow_redirects=True
            )
            is_ok = resp.status_code == 200
            if is_ok:
                logger.info("URL check successful url=%s", normalized)
            else:
                logger.debug("URL check failed url=%s status=%s", normalized, resp.status_code)
            return is_ok
        except requests.RequestException as e:
            logger.debug("URL check exception url=%s error=%s", normalized, str(e))
            return False
    
    def _find_job_listing_page(self, careers_landing_url: str) -> str | None:
        """
        Detect if the career page is just a landing page and try to find the actual job listing page.
        Many career sites have a landing page with a "View Jobs" or "Search Jobs" link.
        """
        try:
            resp = requests.get(
                careers_landing_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html",
                },
                timeout=10,
                allow_redirects=True
            )
            
            if resp.status_code != 200:
                return None
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Common link texts that lead to actual job listings
            job_link_indicators = [
                "view jobs",
                "search jobs",
                "job search",
                "browse jobs",
                "find jobs",
                "see open roles",
                "view open roles",
                "explore jobs",
                "current openings",
                "open positions",
                "see all jobs",
                "all jobs",
                "job opportunities",
                "career opportunities",
                "apply now",
                "join us",
                "vacancies",
            ]
            
            # Look for links with these texts
            for link in soup.find_all("a", href=True):
                link_text = link.get_text(strip=True).lower()
                href = link.get("href", "")
                
                if not href:
                    continue
                
                # Check if link text matches job listing indicators
                if any(indicator in link_text for indicator in job_link_indicators):
                    jobs_url = urljoin(careers_landing_url, href)
                    if jobs_url.rstrip("/") == careers_landing_url.rstrip("/"):
                        continue
                    if not self._looks_like_inner_job_list_url(jobs_url):
                        continue
                    logger.info("Found job listing link text='%s' url=%s", link_text[:50], jobs_url)
                    if self._url_ok(jobs_url):
                        logger.info("Job listing page verified url=%s", jobs_url)
                        return jobs_url
            
            # Also check for forms or buttons that might lead to job search
            for form in soup.find_all("form"):
                action = form.get("action", "")
                if action and any(keyword in action.lower() for keyword in ["search", "jobs", "careers"]):
                    jobs_url = urljoin(careers_landing_url, action)
                    logger.info("Found job search form action=%s", jobs_url)
                    return jobs_url
            
            logger.debug("No job listing page link found on landing page")
            return None
            
        except Exception as e:
            logger.debug("Error finding job listing page error=%s", str(e))
            return None

    def _load_next_data(self, soup: BeautifulSoup) -> dict | None:
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return None
        try:
            return json.loads(script.string)
        except json.JSONDecodeError:
            return None

    def _extract_jobs_from_json_payload(
        self,
        data: object,
        base_url: str,
        company: str,
    ) -> list[JobResult]:
        # Check if this is metadata/categories instead of jobs
        if isinstance(data, dict):
            # Detect category/metadata endpoints
            if any(k in data for k in ["jobCategories", "categories", "filters", "facets", "teams"]):
                logger.debug("Detected metadata/categories response, not job listings")
                return []
        
        jobs_list = data if isinstance(data, list) else None
        if jobs_list is None and isinstance(data, dict):
            # Try common top-level keys
            jobs_list = (
                data.get("jobs")
                or data.get("results")
                or data.get("openings")
                or data.get("data")
                or data.get("postings")
                or data.get("items")
                or data.get("requisitions")
                or data.get("positions")
                or data.get("hits")
            )
            
            # Handle nested structures (e.g., CARS24: data.data[].source)
            if not jobs_list and "data" in data:
                nested = data["data"]
                if isinstance(nested, list):
                    jobs_list = nested
                elif isinstance(nested, dict) and any(k in nested for k in ["results", "items", "jobs"]):
                    jobs_list = nested.get("results") or nested.get("items") or nested.get("jobs")
        
        if not isinstance(jobs_list, list) or not jobs_list:
            return []
        
        results: list[JobResult] = []
        for job in jobs_list:
            if not isinstance(job, dict):
                continue
            
            # Handle nested _source (Elasticsearch-style responses)
            if "_source" in job and isinstance(job["_source"], dict):
                job = job["_source"]
            
            # Handle nested hit (Algolia/search engine responses)
            if "hit" in job and isinstance(job["hit"], dict):
                job = job["hit"]
            
            # Extract title with multiple fallbacks
            title = (
                job.get("title")
                or job.get("jobTitle")
                or job.get("name")
                or job.get("requisitionTitle")
                or job.get("designation")
                or job.get("roleName")
                or job.get("job_title")
                or job.get("position")
                or job.get("position_title")
            )
            
            # Extract ID
            job_id = (
                job.get("id")
                or job.get("_id")
                or job.get("jobId")
                or job.get("reqId")
                or job.get("requisitionId")
            )
            
            # Extract location with multiple fallbacks
            location = job.get("location") or job.get("officeLocationNames")
            if isinstance(location, dict):
                location = location.get("city") or location.get("name") or location.get("state")
            elif isinstance(location, list) and location:
                # Handle array of locations
                if isinstance(location[0], dict):
                    location = location[0].get("name") or location[0].get("city")
                else:
                    location = str(location[0])
            
            # Extract apply URL
            apply_url = (
                job.get("applyUrl")
                or job.get("url")
                or job.get("link")
                or job.get("job_application_url")
                or job.get("applicationUrl")
            )
            
            if not title:
                continue
            if not embedded_record_looks_like_job_posting(job, str(title)):
                continue

            # Generate apply URL if not provided
            if not apply_url:
                if job_id:
                    # Try common URL patterns
                    apply_url = f"{base_url.rstrip('/')}/#/job/{job_id}"
                else:
                    apply_url = base_url

            # Ensure absolute URL
            if apply_url and not str(apply_url).startswith("http"):
                apply_url = urljoin(base_url, str(apply_url))

            external_id = hashlib.sha256(
                f"{base_url}:{job_id or title}".encode("utf-8")
            ).hexdigest()
            posted = _parse_posted_at_from_dict(job)
            results.append(
                JobResult(
                    company=company,
                    role=str(title),
                    location=str(location) if location else None,
                    apply_url=str(apply_url) if apply_url else base_url,
                    ats_type=self.ats_type,
                    external_id=external_id,
                    description=job.get("description") or job.get("jdDisplay"),
                    posted_at=posted,
                )
            )
        return results

    def _extract_jobs_from_embedded_json(self, soup: BeautifulSoup, base_url: str, company: str) -> list[JobResult]:
        """Extract jobs from JSON embedded in script tags (SPAs, window.__DATA__, etc.)."""
        results: list[JobResult] = []
        seen_keys: set[tuple[str, str]] = set()

        def try_extract(obj) -> None:
            if isinstance(obj, list):
                for item in obj:
                    try_extract(item)
            elif isinstance(obj, dict):
                title = obj.get("title") or obj.get("jobTitle") or obj.get("name") or obj.get("position") or obj.get("Title")
                job_id = obj.get("id") or obj.get("jobId") or obj.get("reqId") or obj.get("requisitionId") or obj.get("ReqId")
                loc = obj.get("location") or obj.get("Location")
                if isinstance(loc, dict):
                    loc = loc.get("city") or loc.get("name") or loc.get("City") or str(loc)
                elif isinstance(loc, list) and loc and isinstance(loc[0], dict):
                    loc = loc[0].get("city") or loc[0].get("City") or loc[0].get("name")
                apply_url = obj.get("applyUrl") or obj.get("job_application_url") or obj.get("url") or obj.get("link") or obj.get("JobUrl")
                if title and isinstance(title, str) and len(title) >= 2:
                    if embedded_record_looks_like_job_posting(obj, title):
                        if apply_url and isinstance(apply_url, str) and apply_url.startswith("http"):
                            pass
                        elif job_id is not None:
                            apply_url = apply_url or f"{base_url.rstrip('/')}/#/careers?jd={job_id}"
                            if apply_url and not str(apply_url).startswith("http"):
                                apply_url = urljoin(base_url, str(apply_url))
                        else:
                            apply_url = apply_url or base_url
                            if apply_url and not str(apply_url).startswith("http"):
                                apply_url = urljoin(base_url, str(apply_url))
                        key = (title, str(apply_url or base_url))
                        if key not in seen_keys:
                            seen_keys.add(key)
                            external_id = hashlib.sha256(str(apply_url or base_url).encode("utf-8")).hexdigest()
                            desc = (
                                obj.get("description")
                                or obj.get("jobDescription")
                                or obj.get("jdDisplay")
                                or obj.get("content")
                            )
                            if isinstance(desc, str):
                                desc = desc.strip() or None
                            else:
                                desc = None
                            posted = _parse_posted_at_from_dict(obj)
                            results.append(
                                JobResult(
                                    company=company,
                                    role=title,
                                    location=str(loc) if loc else None,
                                    apply_url=str(apply_url) if apply_url else base_url,
                                    ats_type=self.ats_type,
                                    external_id=external_id,
                                    description=desc,
                                    posted_at=posted,
                                )
                            )
                for v in obj.values():
                    try_extract(v)

        next_data = self._load_next_data(soup)
        if next_data:
            try_extract(next_data)

        for script in soup.find_all("script"):
            if not script.string:
                continue
            raw = script.string.strip()
            if raw.startswith("{") or raw.startswith("["):
                try:
                    try_extract(json.loads(raw))
                except json.JSONDecodeError:
                    pass
                continue
            for prefix in ("window.__DATA__", "window.__INITIAL_STATE__", "window.__PRELOADED_STATE__", "var __JOBS__", "window.jobsData", "__NEXT_DATA__"):
                if prefix in raw and "=" in raw:
                    try:
                        start = raw.find("=", raw.find(prefix)) + 1
                        end = raw.rfind(";")
                        if end == -1:
                            end = len(raw)
                        snippet = raw[start:end].strip()
                        if snippet.startswith("{") or snippet.startswith("["):
                            try_extract(json.loads(snippet))
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break

        logger.info("Embedded JSON extraction found jobs=%d", len(results))
        return results

    def _extract_jobs_generic(self, soup: BeautifulSoup, base_url: str, company: str) -> list[JobResult]:
        """Extract jobs using generic HTML patterns (works for any career page)."""
        results: list[JobResult] = []

        job_selectors = [
            "a[href*='job']",
            "a[href*='position']",
            "a[href*='opening']",
            "a[href*='career']",
            ".job-listing a", ".job-item a", ".job-card a", ".position a",
            "[class*='job'] a", "[class*='position'] a", "[class*='opening'] a",
            "[data-job-id] a", "[data-automation-id*='job'] a",
            "li a[href]", "div[class*='job'] a", "article a",
        ]

        found_links = set()

        for selector in job_selectors:
            try:
                for link in soup.select(selector):
                    href = link.get("href", "").strip()
                    text = link.get_text(strip=True)

                    if not href or not text:
                        continue

                    if any(skip in text.lower() for skip in ['login', 'sign in', 'home', 'about', 'contact', 'privacy', 'terms']):
                        continue

                    if href.startswith("http"):
                        full_url = href
                    elif href.startswith("/"):
                        parsed_base = urlparse(base_url)
                        full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                    else:
                        full_url = urljoin(base_url, href)

                    if full_url in found_links:
                        continue

                    if not self._looks_like_job_url(full_url, text):
                        continue

                    found_links.add(full_url)

                    location = None
                    parent = link.parent
                    if parent:
                        parent_text = parent.get_text(strip=True)
                        for word in parent_text.split():
                            if any(city in word.lower() for city in ['bangalore', 'bengaluru', 'mumbai', 'delhi', 'hyderabad', 'chennai', 'pune', 'remote']):
                                location = word
                                break

                    external_id = hashlib.sha256(full_url.encode("utf-8")).hexdigest()
                    results.append(
                        JobResult(
                            company=company,
                            role=text,
                            location=location,
                            apply_url=full_url,
                            ats_type=self.ats_type,
                            external_id=external_id,
                            description=None,
                        )
                    )

                    logger.debug("Generic extraction found job title='%s' url=%s", text[:50], full_url)
            except Exception as e:
                logger.debug("Selector %s failed: %s", selector, str(e))
                continue

        logger.info("Generic extraction found %d unique job links", len(results))
        return results

    # Playwright: rate limit between requests (seconds)
    _PLAYWRIGHT_SCROLL_DELAY = 0.55
    _PLAYWRIGHT_MAX_SCROLL_ITERATIONS = 25
    _PLAYWRIGHT_LOAD_MORE_ITERATIONS = 15
    _PLAYWRIGHT_NEXT_PAGE_ITERATIONS = 20
    _PLAYWRIGHT_SKIP_PAGE_SIZE = 100
    _PLAYWRIGHT_JOB_DETAIL_DELAY = 1.5

    # Nav/locale link titles to exclude from job listing extraction (lowercase)
    _NAV_TITLE_SKIP = frozenset({
        "jobs", "job", "life at stripe", "benefits", "university", "see open roles",
        "bridge open roles", "privy open roles", "english", "italiano", "deutsch",
        "français", "español", "nederlands", "português", "svenska", "日本語", "简体中文",
        "ไทย", "view jobs", "search jobs", "browse jobs",
        "north america", "latin america", "middle east", "asia pacific", "europe",
        "products", "people", "security", "bridge", "tech programs",
        "risk & financial crimes", "emea", "apac",
    })

    def scrape_careers_listing_for_ingestion(
        self,
        careers_url: str,
        company: str,
        *,
        max_scroll_rounds: int | None = None,
        max_load_more_rounds: int | None = None,
        max_next_page_rounds: int | None = None,
        listing_max_pages: int | None = None,
        user_agent: str | None = None,
        default_timeout_ms: int | None = None,
    ) -> list[JobResult]:
        """
        Public entry for job-corpus ingestion: Playwright listing pass with YAML-driven caps
        (scroll / load-more / pagination). Used by `jobscrapping.scrapping_algorithms.company_careers`.
        """
        return self._extract_jobs_with_playwright(
            careers_url,
            company,
            max_scroll_rounds=max_scroll_rounds,
            max_load_more_rounds=max_load_more_rounds,
            max_next_page_rounds=max_next_page_rounds,
            listing_max_pages=listing_max_pages,
            user_agent=user_agent,
            default_timeout_ms=default_timeout_ms,
        )

    def extract_jobs_from_careers_url(
        self,
        url: str,
        company: str,
        *,
        role: str = "",
        skills: list[str] | None = None,
        use_playwright: bool = False,
    ) -> tuple[list[JobResult], dict[str, Any]]:
        """
        Company-search pipeline on a known careers URL: HTTP/JSON, iframe ATS, then ATS adapters
        (Greenhouse, Lever, Workday, Ashby, …), optionally Playwright for generic HTML.

        Used by unified job ingest alongside :meth:`scrape_careers_listing_for_ingestion` (which
        only runs the Playwright listing pass with YAML caps). When ``use_playwright`` is False,
        this avoids a second browser while still harvesting API-backed boards.
        """
        sk = skills if skills is not None else []
        return self._extract_jobs_from_url(url, company, role, sk, use_playwright=use_playwright)

    def _try_lever_public_api(self, careers_url: str, company: str) -> list[JobResult] | None:
        """
        Lever exposes an unauthenticated JSON API — avoids Playwright timeouts on jobs.lever.co SPAs.
        Returns a list (possibly empty) on success, or None to fall back to the browser path.
        """
        try:
            parsed = urlparse(careers_url)
            host = (parsed.netloc or "").lower()
            if "lever.co" not in host:
                return None
            parts = [p for p in (parsed.path or "").strip("/").split("/") if p]
            if not parts:
                return None
            slug = parts[0]
            api_url = f"https://api.lever.co/v0/postings/{slug}"
            t_out = max(15, min(90, int(self.timeout_seconds)))
            resp = requests.get(
                api_url,
                timeout=t_out,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; HiremateCareerIngest/1.0; +https://example.invalid)",
                    "Accept": "application/json",
                },
            )
            if resp.status_code != 200:
                logger.info("Lever API skip slug=%s status=%s", slug, resp.status_code)
                return None
            data = resp.json()
            if not isinstance(data, list):
                return None
            out: list[JobResult] = []
            for posting in data:
                if not isinstance(posting, dict):
                    continue
                title = (posting.get("text") or "").strip()
                apply_url = (posting.get("hostedUrl") or "").strip() or (posting.get("applyUrl") or "").strip()
                if not title or not apply_url:
                    continue
                loc: str | None = None
                cats = posting.get("categories")
                if isinstance(cats, dict):
                    loc = cats.get("location")
                    if not loc:
                        al = cats.get("allLocations")
                        if isinstance(al, list) and al:
                            loc = str(al[0]).strip() or None
                wt = posting.get("workplaceType")
                if isinstance(wt, str) and wt.lower() == "remote" and not loc:
                    loc = "Remote"
                ext = hashlib.sha256(apply_url.encode("utf-8")).hexdigest()
                out.append(
                    JobResult(
                        company=company,
                        role=title[:300],
                        location=loc,
                        apply_url=apply_url,
                        ats_type=self.ats_type,
                        external_id=ext,
                        description=None,
                    )
                )
            logger.info("Lever public API slug=%s jobs=%d", slug, len(out))
            return self.dedupe_jobs(out)
        except Exception as exc:
            logger.debug("Lever public API failed url=%s error=%s", careers_url, exc)
            return None

    def _extract_jobs_with_playwright(
        self,
        careers_url: str,
        company: str,
        *,
        max_scroll_rounds: int | None = None,
        max_load_more_rounds: int | None = None,
        max_next_page_rounds: int | None = None,
        listing_max_pages: int | None = None,
        user_agent: str | None = None,
        default_timeout_ms: int | None = None,
    ) -> list[JobResult]:
        """
        Use a real browser (Playwright) to scrape career pages. Supports SPAs, Next.js, infinite scroll,
        and "Load more" / pagination. Structure-agnostic extraction via job-like links and repeated blocks.
        Optional kwargs override class defaults (ingestion / portals.yml settings).
        """
        scroll_cap = max_scroll_rounds if max_scroll_rounds is not None else self._PLAYWRIGHT_MAX_SCROLL_ITERATIONS
        load_more_cap = max_load_more_rounds if max_load_more_rounds is not None else self._PLAYWRIGHT_LOAD_MORE_ITERATIONS
        next_cap = max_next_page_rounds if max_next_page_rounds is not None else self._PLAYWRIGHT_NEXT_PAGE_ITERATIONS
        url_page_cap = listing_max_pages if listing_max_pages is not None else 25
        pw_timeout_ms = int(default_timeout_ms) if default_timeout_ms else 20000
        ua = (
            user_agent
            or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        goto_timeout_ms = min(25000, max(5000, pw_timeout_ms))

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        except ImportError:
            logger.warning("Playwright not installed; skipping browser-based extraction")
            return []

        logger.info("Playwright extracting jobs from url=%s", careers_url)
        lever_jobs = self._try_lever_public_api(careers_url, company)
        if lever_jobs is not None:
            return lever_jobs

        results: list[JobResult] = []
        html = ""

        def _nav_and_wait(page, url: str) -> bool:
            for attempt in range(2):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
                    # Do not use networkidle — SPAs and analytics keep sockets open and stall for the full timeout.
                    page.wait_for_timeout(950)
                    return True
                except PlaywrightTimeout:
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=5000)
                        page.wait_for_timeout(500)
                        return True
                    except Exception:
                        pass
                except Exception as e:
                    logger.debug("Playwright goto attempt %d failed: %s", attempt + 1, e)
            return False

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                )
                try:
                    context = browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent=ua,
                    )
                    # Faster loads on JS career sites: still run scripts/styles; skip heavy assets.
                    try:

                        def _route_assets(route):
                            if route.request.resource_type in ("image", "media", "font"):
                                route.abort()
                            else:
                                route.continue_()

                        context.route("**/*", _route_assets)
                    except Exception:
                        pass
                    page = context.new_page()
                    page.set_default_timeout(pw_timeout_ms)

                    if not _nav_and_wait(page, careers_url):
                        logger.warning("Playwright navigation failed for %s", careers_url)
                        return []

                    # Hash / client-side routers (e.g. /#/careers) need extra time for JS to render listings.
                    if "#" in (page.url or "") or "#" in careers_url:
                        page.wait_for_timeout(1800)
                        try:
                            page.wait_for_load_state("load", timeout=15000)
                        except Exception:
                            pass
                        page.wait_for_timeout(500)

                    nav_skip_list = list(self._NAV_TITLE_SKIP)
                    seen_urls: set[str] = set()

                    def _append_entries_to_results(entries, results_list, seen_urls_set):
                        added = 0
                        for entry in entries if isinstance(entries, list) else []:
                            if not isinstance(entry, dict):
                                continue
                            url = entry.get("url") or entry.get("href")
                            title = entry.get("title") or ""
                            if not isinstance(title, str):
                                title = str(title) if title is not None else ""
                            if not isinstance(url, str):
                                url = str(url) if url is not None else ""
                            url = _normalize_job_listing_url(url.strip())
                            title = _polish_listing_title(title)
                            if not url or not title or url in seen_urls_set:
                                continue
                            if title.strip().lower() in self._NAV_TITLE_SKIP:
                                continue
                            if not listing_title_looks_like_job_posting(title):
                                continue
                            parsed = urlparse(str(url))
                            path = (parsed.path or "").rstrip("/")
                            if path in ("/jobs", "/job", "/careers", "/career") or path.endswith("/search"):
                                continue
                            if re.search(r"^/[a-z]{2}(-[a-z]{2})?/jobs/search", path):
                                continue
                            seen_urls_set.add(url)
                            external_id = hashlib.sha256(str(url).encode("utf-8")).hexdigest()
                            loc = entry.get("location")
                            if isinstance(loc, str):
                                lclean = loc.strip()
                                if re.search(r"Remote\s*\$|^\$|€\d|£\d|Product$|^GTM\s*•", lclean, re.I):
                                    loc = None
                                elif len(lclean) < 2:
                                    loc = None
                                else:
                                    loc = lclean[:200]
                            else:
                                loc = None
                            results_list.append(
                                JobResult(
                                    company=company,
                                    role=title,
                                    location=loc,
                                    apply_url=url,
                                    ats_type=self.ats_type,
                                    external_id=external_id,
                                    description=None,
                                )
                            )
                            added += 1
                        return added

                    def _pull_dom_jobs() -> int:
                        raw = page.evaluate(
                            CAREER_PLAYWRIGHT_JOB_LINKS_JS,
                            {"base": page.url, "navSkip": nav_skip_list},
                        )
                        return _append_entries_to_results(raw, results, seen_urls)

                    _pull_dom_jobs()

                    # Wait for list: job card or link with job/career/position in href
                    list_selectors = [
                        'div[class*="job"]',
                        'div[class*="position"]',
                        'div[class*="opening"]',
                        'article[class*="job"]',
                        'li[class*="job"]',
                        'a[href*="/job"]',
                        'a[href*="/careers"]',
                        'a[href*="/position"]',
                        '[data-job-id]',
                        '[data-automation-id*="job"]',
                    ]
                    for sel in list_selectors:
                        try:
                            page.wait_for_selector(sel, timeout=6000)
                            logger.info("Playwright list detected via selector: %s", sel)
                            break
                        except PlaywrightTimeout:
                            continue
                    _pull_dom_jobs()

                    # Click "View Jobs" / "See Open Roles" once to land on listing, then paginate with "Load more" / "Show more"
                    cta_selectors = [
                        'a:has-text("View Jobs")',
                        'a:has-text("Search Jobs")',
                        'a:has-text("Browse Jobs")',
                        'a:has-text("See Open Roles")',
                        'button:has-text("View Jobs")',
                    ]
                    for sel in cta_selectors:
                        try:
                            loc = page.locator(sel).first
                            if loc.count() > 0:
                                loc.click(timeout=3000)
                                page.wait_for_timeout(1100)
                                logger.info("Playwright clicked CTA: %s", sel)
                                break
                        except Exception:
                            continue
                    _pull_dom_jobs()

                    # Pagination: repeatedly click "Load more" / "Show more" / "Next" until no more
                    load_more_selectors = [
                        'button:has-text("Load more")',
                        'button:has-text("Load More")',
                        'a:has-text("Load more")',
                        'a:has-text("Load More")',
                        'button:has-text("Show more")',
                        'button:has-text("Show More")',
                        'a:has-text("Show more")',
                        '[aria-label*="Load more"]',
                        '[aria-label*="Show more"]',
                        'button:has-text("Next")',
                        'a:has-text("Next")',
                        '[data-testid*="load-more"]',
                        '[data-testid*="show-more"]',
                    ]
                    for _ in range(load_more_cap):
                        clicked = False
                        for sel in load_more_selectors:
                            try:
                                loc = page.locator(sel).first
                                if loc.count() > 0 and loc.is_visible():
                                    loc.click(timeout=3000)
                                    page.wait_for_timeout(700)
                                    clicked = True
                                    logger.info("Playwright pagination clicked: %s", sel)
                                    break
                            except Exception:
                                continue
                        if not clicked:
                            break
                        _pull_dom_jobs()

                    # Infinite scroll: merge after each round so lazy-rendered / SPA rows are not skipped.
                    prev_count = -1
                    stable_rounds = 0
                    min_scroll_before_stable = min(5, max(1, scroll_cap // 3))
                    scroll_i = 0
                    for _ in range(scroll_cap):
                        scroll_i += 1
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(int(self._PLAYWRIGHT_SCROLL_DELAY * 1000))
                        _pull_dom_jobs()
                        count = page.evaluate(
                            """() => {
                            const as = document.querySelectorAll(
                              'a[href*="job"], a[href*="career"], a[href*="position"], a[href*="opening"], a[href*="gh_jid"]'
                            );
                            const seen = new Set();
                            as.forEach(a => { if (a.href && (a.textContent||'').trim().length > 2) seen.add(a.href); });
                            return seen.size;
                            }"""
                        )
                        if isinstance(count, int):
                            if count == prev_count:
                                stable_rounds += 1
                                if stable_rounds >= 3 and scroll_i >= min_scroll_before_stable:
                                    break
                            else:
                                stable_rounds = 0
                            prev_count = count
                    _pull_dom_jobs()
                    logger.info("Playwright DOM link pass collected %d jobs (pre-pagination)", len(results))

                    def _collect_page_entries():
                        return page.evaluate(
                            CAREER_PLAYWRIGHT_JOB_LINKS_JS,
                            {"base": page.url, "navSkip": nav_skip_list},
                        )

                    # Pagination (generic for all sites): URL params (skip / offset / page) then "Next" clicks
                    parsed_careers = urlparse(careers_url)
                    base_search = f"{parsed_careers.scheme}://{parsed_careers.netloc}{parsed_careers.path.rstrip('/') or '/'}"
                    page_size = self._PLAYWRIGHT_SKIP_PAGE_SIZE
                    max_pages = url_page_cap

                    # 1) URL pagination: try ?skip=, ?offset=, ?page= (generic; works for Stripe, etc.)
                    for param_name, start, step in [
                        ("skip", page_size, page_size),
                        ("offset", page_size, page_size),
                        ("page", 2, 1),
                    ]:
                        any_added = False
                        for i in range(max_pages):
                            n = start + i * step
                            sep = "?" if "?" not in base_search else "&"
                            url = f"{base_search}{sep}{param_name}={n}"
                            try:
                                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                                page.wait_for_timeout(800)
                            except Exception as e:
                                logger.debug("Pagination %s=%s failed: %s", param_name, n, e)
                                break
                            entries = _collect_page_entries()
                            added = _append_entries_to_results(entries, results, seen_urls)
                            any_added = any_added or (added > 0)
                            if added > 0:
                                logger.info("Pagination %s=%s added %d jobs total=%d", param_name, n, added, len(results))
                            if added == 0 and n > start:
                                break
                        if any_added:
                            break

                    # 2) "Next" link/button pagination (generic for all sites)
                    next_selectors = [
                        'a:has-text("Next")',
                        'button:has-text("Next")',
                        '[aria-label*="Next"]',
                        '[aria-label*="next page"]',
                        'a[rel="next"]',
                        'nav a:has-text("Next")',
                    ]
                    for _ in range(next_cap):
                        clicked = False
                        for sel in next_selectors:
                            try:
                                loc = page.locator(sel).first
                                if loc.count() > 0 and loc.is_visible():
                                    loc.click(timeout=3000)
                                    page.wait_for_timeout(1000)
                                    clicked = True
                                    logger.info("Playwright clicked Next: %s", sel)
                                    break
                            except Exception:
                                continue
                        if not clicked:
                            break
                        entries = _collect_page_entries()
                        added = _append_entries_to_results(entries, results, seen_urls)
                        if added == 0:
                            break

                    if results:
                        logger.info("Playwright total jobs after pagination: %d", len(results))

                    html = page.content()
                    if not results:
                        iframe_results = self._extract_from_iframes(page, careers_url, company)
                        if iframe_results:
                            results.extend(iframe_results)

                finally:
                    browser.close()

            # SPAs often hydrate job rows from __NEXT_DATA__ / window state — merge even when DOM links exist.
            if html:
                soup = BeautifulSoup(html, "html.parser")
                embedded_results = self._extract_jobs_from_embedded_json(soup, careers_url, company)
                if embedded_results:
                    results.extend(embedded_results)
                if not results:
                    generic_results = self._extract_jobs_generic(soup, careers_url, company)
                    if generic_results:
                        results.extend(generic_results)
                    table_results = self._extract_jobs_from_tables(soup, careers_url, company)
                    if table_results:
                        results.extend(table_results)

            return self.dedupe_jobs(results)

        except Exception as e:
            logger.error("Playwright extraction failed url=%s error=%s", careers_url, str(e))
            return []

    def fetch_job_description(self, url: str) -> Optional[str]:
        """Try HTTP first; use Playwright for SPA job pages when content is minimal."""
        text = super().fetch_job_description(url)
        if text and len(text.strip()) >= 200:
            return text
        try:
            resp = requests.get(
                url,
                timeout=self.timeout_seconds,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
            )
            if resp.status_code != 200:
                return text
            html = resp.text or ""
            # SPA shell: little or no server-rendered job content
            if ("#root" in html or "__next" in html or 'id="root"' in html) and (not text or len((text or "").strip()) < 200):
                pw_text = self._fetch_description_with_playwright(url)
                if pw_text and len(pw_text.strip()) > 100:
                    return pw_text
        except Exception as e:
            logger.debug("SPA description check failed url=%s error=%s", url, e)
        return text

    def _fetch_description_with_playwright(self, job_url: str) -> Optional[str]:
        """Fetch job description by rendering the page in a browser (for SPAs)."""
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        except ImportError:
            return None
        time.sleep(self._PLAYWRIGHT_JOB_DETAIL_DELAY)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
                try:
                    page = browser.new_page()
                    page.set_default_timeout(15000)
                    page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(1200)
                    desc_selectors = [
                        "[data-job-description]",
                        ".job-description",
                        ".posting-description",
                        ".description",
                        ".content",
                        "[data-automation-id='job-posting']",
                        "main",
                        "#content",
                        ".job-posting",
                    ]
                    for sel in desc_selectors:
                        try:
                            loc = page.locator(sel)
                            if loc.count() > 0:
                                raw = loc.first.inner_text()
                                if raw and len(raw.strip()) > 100:
                                    return re.sub(r"\s+", " ", raw.strip())
                        except Exception:
                            continue
                    body = page.locator("body").inner_text()
                    if body and len(body.strip()) > 100:
                        return re.sub(r"\s+", " ", body.strip())[:15000]
                finally:
                    browser.close()
        except Exception as e:
            logger.debug("Playwright description fetch failed url=%s error=%s", job_url, e)
        return None

    def _extract_from_iframes(self, page, base_url: str, company: str) -> list[JobResult]:
        """Extract jobs from iframes (common for embedded job widgets)."""
        results = []
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeout
            
            iframes = page.frames
            logger.info("Playwright found %d iframes", len(iframes))
            
            for idx, iframe in enumerate(iframes):
                if idx == 0:  # Skip main frame
                    continue
                
                try:
                    try:
                        iframe.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                    page.wait_for_timeout(600)
                    iframe_html = iframe.content()
                    
                    if len(iframe_html) > 1000:  # Only process substantial iframes
                        logger.info("Playwright processing iframe %d length=%d", idx, len(iframe_html))
                        iframe_soup = BeautifulSoup(iframe_html, "html.parser")
                        iframe_results = self._extract_jobs_generic(iframe_soup, base_url, company)
                        if iframe_results:
                            logger.info("Playwright extracted %d jobs from iframe %d", len(iframe_results), idx)
                            results.extend(iframe_results)
                except PlaywrightTimeout:
                    continue
                except Exception as e:
                    logger.debug("Iframe %d extraction error: %s", idx, str(e))
                    continue
        except Exception as e:
            logger.debug("Iframe extraction failed: %s", str(e))
        
        return results
    
    def _extract_jobs_from_tables(self, soup: BeautifulSoup, base_url: str, company: str) -> list[JobResult]:
        """Extract jobs from table structures."""
        results = []
        
        for table in soup.find_all("table"):
            tbody = table.find("tbody") or table
            rows = tbody.find_all("tr")
            
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue
                
                # First column usually has the job title
                title = tds[0].get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                
                # Skip non-job rows
                if any(skip in title.lower() for skip in ["apply now", "apply", "login", "search"]):
                    continue
                if not listing_title_looks_like_job_posting(title):
                    continue

                # Try to find link
                link_el = tr.find("a", href=True)
                href = link_el.get("href", "").strip() if link_el else ""
                if href and not href.startswith("http"):
                    href = urljoin(base_url, href)
                
                apply_url = href or base_url
                
                # Try to extract location (usually in 2nd or 3rd column)
                location = None
                if len(tds) >= 2:
                    location = tds[1].get_text(strip=True) if len(tds[1].get_text(strip=True)) < 100 else None
                if not location and len(tds) >= 3:
                    location = tds[2].get_text(strip=True) if len(tds[2].get_text(strip=True)) < 100 else None
                
                external_id = hashlib.sha256(apply_url.encode("utf-8")).hexdigest()
                
                results.append(
                    JobResult(
                        company=company,
                        role=title,
                        location=location,
                        apply_url=apply_url,
                        ats_type=self.ats_type,
                        external_id=external_id,
                        description=None,
                    )
                )
        
        return results

    def _looks_like_job_url(self, url: str, title: str) -> bool:
        """Check if URL and title look like a job posting."""
        url_lower = url.lower()
        title_lower = title.lower()

        job_url_keywords = ['job', 'position', 'opening', 'career', 'role', 'opportunity', 'vacancy', 'jd=', 'reqid=', 'id=']
        has_job_keyword = any(keyword in url_lower for keyword in job_url_keywords)
        has_hash_route = '#' in url and ('career' in url_lower or 'job' in url_lower)
        if not (has_job_keyword or has_hash_route):
            return False

        skip_words = ['login', 'sign in', 'home', 'about', 'contact', 'privacy', 'terms', 'apply', 'submit']
        if any(skip in title_lower for skip in skip_words):
            return False

        return listing_title_looks_like_job_posting(title)
