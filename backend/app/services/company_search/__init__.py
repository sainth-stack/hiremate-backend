"""
Career page discovery and job scraping (ATS adapters, HTML/Playwright).

Used by ``company_search_service`` for link resolution and job listing extraction.
"""
from backend.app.services.company_search.base import BaseATSScraper, JobResult
from backend.app.services.company_search.career import CareerPageScraper
from backend.app.services.company_search.greenhouse import GreenhouseScraper
from backend.app.services.company_search.lever import LeverScraper
from backend.app.services.company_search.job_description_scraper import (
    parse_job_description_from_html,
)
from backend.app.services.company_search.workday import WorkdayScraper

__all__ = [
    "BaseATSScraper",
    "CareerPageScraper",
    "GreenhouseScraper",
    "JobResult",
    "LeverScraper",
    "WorkdayScraper",
    "parse_job_description_from_html",
]
