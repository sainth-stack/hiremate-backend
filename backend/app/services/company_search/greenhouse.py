from __future__ import annotations

import hashlib
from typing import Optional
from urllib.parse import urljoin

import logging
import requests
from bs4 import BeautifulSoup

from backend.app.services.company_search.base import BaseATSScraper, JobResult


logger = logging.getLogger(__name__)


class GreenhouseScraper(BaseATSScraper):
    ats_type = "greenhouse"

    def discover_careers_url(self, company: str) -> Optional[str]:
        slug = self.normalize_company(company)
        url = f"https://boards.greenhouse.io/{slug}"
        logger.info("Greenhouse discover url=%s", url)
        resp = requests.get(url, timeout=self.timeout_seconds)
        if resp.status_code != 200:
            logger.info("Greenhouse not found status=%s", resp.status_code)
            return None
        return url

    def search_jobs(self, company: str, role: str, skills: list[str]) -> list[JobResult]:
        careers_url = self.discover_careers_url(company)
        if not careers_url:
            return []

        resp = requests.get(careers_url, timeout=self.timeout_seconds)
        if resp.status_code != 200:
            logger.info("Greenhouse fetch failed status=%s", resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[JobResult] = []
        skills_required = bool(skills)
        for opening in soup.select(".opening"):
            link = opening.find("a")
            if not link or not link.text:
                continue
            title = link.text.strip()
            if not self.role_matches(title, role):
                continue
            href = link.get("href", "").strip()
            if not href:
                continue
            apply_url = urljoin(careers_url, href)
            location_el = opening.select_one(".location")
            location = location_el.text.strip() if location_el and location_el.text else None
            description = self.fetch_job_description(apply_url) if skills_required else None
            external_id = hashlib.sha256(apply_url.encode("utf-8")).hexdigest()
            results.append(
                JobResult(
                    company=company,
                    role=title,
                    location=location,
                    apply_url=apply_url,
                    ats_type=self.ats_type,
                    external_id=external_id,
                    description=description,
                )
            )

        logger.info("Greenhouse results=%d", len(results))
        return self.dedupe_jobs(results)
