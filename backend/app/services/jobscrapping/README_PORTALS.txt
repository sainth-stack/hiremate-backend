Portal config for job ingestion (career pages + public URL feeds)
================================================================

Primary file
------------
- company.json — Edit this (tracked_companies, public_urls, title_filter, search_queries, settings).

Scraping code layout (backend/app/services/jobscrapping/scrapping_algorithms/)
-------------------------------------------------------------------------------
- company_careers.py — Playwright pass over tracked_companies / careers_url
- live_urls.py — HTTP/JSON public feeds (Remotive, generic JSON)
- linkedin.py, naukri.py — stubs for future portal-specific ingestion (ToS / rate limits apply)

Loader resolution (backend/app/services/jobscrapping/config.py)
-----------------------------------------------------------------
1. PORTALS_CONFIG env if set (path to .yml / .yaml / .json)
2. Else bundled company.json next to this package
3. Else company_source.yml (optional YAML)
4. Else repo data/portals.yml or data/portals.example.yml

How data gets into the DB
-------------------------
1) POST .../ingest/career-pages
   - Runs Playwright listing scrape for every enabled company with careers_url.
   - scan_method: websearch does NOT skip scraping; scan_query is unused on this route.
   - Response includes websearch_config_rows (count of config rows tagged websearch) and websearch_skipped (always 0).
   - search_queries in JSON are NOT executed by the backend yet (reserved for a future route).

2) POST .../ingest/public-urls
   - Fetches HTTP/JSON feeds listed under public_urls (e.g. Remotive).

For “websearch” companies and global search_queries you need either a dedicated ingest
implementation (e.g. search API + parser) or use the separate career-ops / web UI scanner
if your project exposes it — the FastAPI ingest routes above do not run WebSearch today.

Two logical groups (same file)
------------------------------
1) Career / Playwright:  tracked_companies
2) Public HTTP feeds:    public_urls

Optional nested shape (JSON or YAML):
{
  "career_pages": {
    "tracked_companies": [ ... ],
    "title_filter": { ... }
  },
  "public_urls": [ ... ]
}

JOB_SOURCES_CONFIG still merges extra public_urls from legacy JSON when set.
