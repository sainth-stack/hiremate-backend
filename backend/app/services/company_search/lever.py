from __future__ import annotations

import hashlib
from typing import Optional

import logging
import requests
from bs4 import BeautifulSoup

from backend.app.services.company_search.base import BaseATSScraper, JobResult


logger = logging.getLogger(__name__)


class LeverScraper(BaseATSScraper):
    ats_type = "lever"

    def discover_careers_url(self, company: str) -> Optional[str]:
        slug = self.normalize_company(company)
        url = f"https://jobs.lever.co/{slug}"
        logger.info("Lever discover url=%s", url)
        resp = requests.get(url, timeout=self.timeout_seconds)
        if resp.status_code != 200:
            logger.info("Lever not found status=%s", resp.status_code)
            return None
        return url

    def search_jobs(self, company: str, role: str, skills: list[str]) -> list[JobResult]:
        careers_url = self.discover_careers_url(company)
        if not careers_url:
            return []

        resp = requests.get(careers_url, timeout=self.timeout_seconds)
        if resp.status_code != 200:
            logger.info("Lever fetch failed status=%s", resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[JobResult] = []
        skills_required = bool(skills)
        for posting in soup.select(".posting"):
            title_el = posting.select_one("a.posting-title")
            if not title_el or not title_el.text:
                continue
            title = title_el.text.strip()
            if not self.role_matches(title, role):
                continue
            apply_url = title_el.get("href", "").strip()
            if not apply_url:
                continue
            location_el = posting.select_one(".posting-categories .sort-by-location")
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

        logger.info("Lever results=%d", len(results))
        return self.dedupe_jobs(results)
