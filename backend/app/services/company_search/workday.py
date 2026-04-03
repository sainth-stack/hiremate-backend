from __future__ import annotations

import hashlib
from typing import Optional

import logging
import requests
from bs4 import BeautifulSoup

from backend.app.services.company_search.base import BaseATSScraper, JobResult


logger = logging.getLogger(__name__)


class WorkdayScraper(BaseATSScraper):
    ats_type = "workday"

    def discover_careers_url(self, company: str) -> Optional[str]:
        slug = self.normalize_company(company)
        candidates = [
            f"https://{slug}.wd5.myworkdayjobs.com/{slug}",
            f"https://{slug}.wd5.myworkdayjobs.com/en-US/{slug}",
            f"https://{slug}.wd1.myworkdayjobs.com/{slug}",
            f"https://{slug}.wd1.myworkdayjobs.com/en-US/{slug}",
        ]
        for url in candidates:
            logger.info("Workday discover url=%s", url)
            resp = requests.get(url, timeout=self.timeout_seconds)
            if resp.status_code == 200:
                return url
        return None

    def search_jobs(self, company: str, role: str, skills: list[str]) -> list[JobResult]:
        careers_url = self.discover_careers_url(company)
        if not careers_url:
            return []

        resp = requests.get(careers_url, timeout=self.timeout_seconds)
        if resp.status_code != 200:
            logger.info("Workday fetch failed status=%s", resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[JobResult] = []

        skills_required = bool(skills)
        for card in soup.select("[data-automation-id='jobCard']"):
            title_el = card.select_one("[data-automation-id='jobTitle']")
            if not title_el or not title_el.text:
                continue
            title = title_el.text.strip()
            if not self.role_matches(title, role):
                continue
            link = title_el.get("href") or title_el.parent.get("href") if title_el.parent else None
            if not link:
                continue
            apply_url = link if link.startswith("http") else f"https://{careers_url.split('/')[2]}{link}"
            location_el = card.select_one("[data-automation-id='locations']")
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

        logger.info("Workday results=%d", len(results))
        return self.dedupe_jobs(results)
