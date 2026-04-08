"""
Internal ingestion routes (scheduler / ops). Auth: `X-Ingest-Secret` header.

Response counters: `total_inserted` matches `inserted` for a run; `total_filtered` matches
`filtered_out` (title_filter drops). See plan.md.
"""
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_db
from backend.app.services.jobscrapping import (
    run_career_pages_ingestion,
    run_public_urls_ingestion,
    run_unified_companies_ingestion,
)
from backend.app.services.jobscrapping.ingest_lock import ingest_route_lock

router = APIRouter(prefix="/jobs", tags=["jobs-ingest"])


def _lock_career_pages():
    with ingest_route_lock("career-pages"):
        yield


def _lock_public_urls():
    with ingest_route_lock("public-urls"):
        yield


def _lock_unified():
    with ingest_route_lock("unified-companies"):
        yield


class IngestBody(BaseModel):
    dry_run: bool = Field(False, description="If true, do not commit DB writes.")


def verify_ingest_secret(
    x_ingest_secret: str | None = Header(None, alias="X-Ingest-Secret"),
) -> None:
    secret = (settings.ingest_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion is not configured (set INGEST_SECRET).",
        )
    if not x_ingest_secret or x_ingest_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Ingest-Secret header.",
        )


@router.post("/ingest/career-pages")
def ingest_career_pages(
    body: IngestBody,
    db: Session = Depends(get_db),
    _: None = Depends(verify_ingest_secret),
    __: None = Depends(_lock_career_pages),
) -> dict[str, Any]:
    m = run_career_pages_ingestion(db, dry_run=body.dry_run)
    return m.as_response()


@router.post("/ingest/public-urls")
def ingest_public_urls(
    body: IngestBody,
    db: Session = Depends(get_db),
    _: None = Depends(verify_ingest_secret),
    __: None = Depends(_lock_public_urls),
) -> dict[str, Any]:
    m = run_public_urls_ingestion(db, dry_run=body.dry_run)
    return m.as_response()


@router.post("/ingest/companies-unified")
def ingest_companies_unified(
    body: IngestBody,
    db: Session = Depends(get_db),
    _: None = Depends(verify_ingest_secret),
    __: None = Depends(_lock_unified),
) -> dict[str, Any]:
    """
    Per tracked company: **parallel** portal tasks (``settings.unified_ingest.portal_parallelism``):
    career Playwright listing, **company-search pipeline** on the same URL (HTTP + ATS APIs such as
    Greenhouse/Lever/Workday when detected), optional second site URL, matching ``public_urls`` rows,
    Indeed RSS, and best-effort LinkedIn / Naukri. Tune ``settings.unified_ingest.company_search``
    (role/skills/location; ``use_playwright`` avoids duplicate browser by default).
    """
    m = run_unified_companies_ingestion(db, dry_run=body.dry_run)
    return m.as_response()
