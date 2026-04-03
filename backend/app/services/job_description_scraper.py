"""Backward-compatible re-export; implementation is under ``company_search``."""
from backend.app.services.company_search.job_description_scraper import parse_job_description_from_html

__all__ = ["parse_job_description_from_html"]
