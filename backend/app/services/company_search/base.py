from __future__ import annotations

import html
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class JobResult:
    company: str
    role: str
    location: Optional[str]
    apply_url: str
    ats_type: str
    external_id: str
    description: Optional[str]


class BaseATSScraper(ABC):
    ats_type: str

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def discover_careers_url(self, company: str) -> Optional[str]:
        raise NotImplementedError

    @abstractmethod
    def search_jobs(self, company: str, role: str, skills: list[str]) -> list[JobResult]:
        raise NotImplementedError

    @staticmethod
    def normalize_company(company: str) -> str:
        return re.sub(r"[^a-z0-9]", "", company.strip().lower())

    @staticmethod
    def role_matches(title: str, role: str) -> bool:
        return role.strip().lower() in title.strip().lower()

    @staticmethod
    def location_matches(job_location: Optional[str], filter_loc: str) -> bool:
        """When ``filter_loc`` is empty, all jobs pass. Otherwise require overlap with scraped location text."""
        fl = (filter_loc or "").strip().lower()
        if not fl:
            return True
        if job_location is None or not str(job_location).strip():
            return False
        jl = str(job_location).strip().lower()
        if fl in jl or jl in fl:
            return True
        noise = {"the", "a", "an", "and", "or", "of", "in", "at", "to", "remote", "usa", "uk", "eu", "emea", "apac"}
        for part in re.split(r"[,;/|]+", fl):
            part = part.strip()
            if len(part) < 2 or part in noise:
                continue
            if part in jl:
                return True
        for tok in re.split(r"[\s,]+", fl):
            tok = tok.strip()
            if len(tok) > 2 and tok not in noise and tok in jl:
                return True
        return False

    @staticmethod
    def dedupe_jobs(items: Iterable[JobResult]) -> list[JobResult]:
        seen: set[str] = set()
        result: list[JobResult] = []
        for item in items:
            if item.external_id in seen:
                continue
            seen.add(item.external_id)
            result.append(item)
        return result

    def fetch_job_description(self, url: str) -> Optional[str]:
        try:
            resp = requests.get(url, timeout=self.timeout_seconds)
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        selectors = [
            "#content",
            ".content",
            ".posting-description",
            ".job-posting",
            "[data-automation-id='job-posting']",
        ]
        text = ""
        for selector in selectors:
            node = soup.select_one(selector)
            if node and node.get_text(strip=True):
                text = node.get_text(" ", strip=True)
                break
        if not text:
            next_text = self._extract_next_data_text(soup)
            if next_text:
                return next_text
        if not text:
            body = soup.body
            text = body.get_text(" ", strip=True) if body else ""
        return text or None

    @staticmethod
    def _extract_next_data_text(soup: BeautifulSoup) -> Optional[str]:
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return None
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            return None
        job = (
            data.get("props", {})
            .get("pageProps", {})
            .get("job", None)
        )
        if not isinstance(job, dict):
            return None
        for key in ("content", "description", "jobDescription"):
            value = job.get(key)
            if isinstance(value, str) and value.strip():
                return BaseATSScraper._html_to_text(value)
        return None

    @staticmethod
    def _html_to_text(raw_html: str) -> str:
        unescaped = html.unescape(raw_html)
        soup = BeautifulSoup(unescaped, "html.parser")
        return soup.get_text(" ", strip=True)
