"""
Scraping algorithms for job ingestion (see also ``README_PORTALS.txt``).

- **Company careers** — Playwright listing pass per ``tracked_companies`` / ``careers_url``
  (:mod:`company_careers`).
- **Live URLs** — HTTP/JSON public feeds (:mod:`live_urls`).
- **Future** — LinkedIn and Naukri (:mod:`linkedin`, :mod:`naukri`); stubs until wired into config.

Import submodules directly, e.g. ``from backend.app.services.jobscrapping.scrapping_algorithms import linkedin``.
"""
from __future__ import annotations

from .company_careers import scrape_enabled_companies, scrape_single_company_careers
from .live_urls import fetch_all_public_feeds

# Portal keys: linkedin/naukri also wired via ``unified_ingest`` (see ``third_party_job_feeds``).
FUTURE_PORTALS = ("linkedin", "naukri")

__all__ = [
    "FUTURE_PORTALS",
    "fetch_all_public_feeds",
    "scrape_enabled_companies",
    "scrape_single_company_careers",
]
