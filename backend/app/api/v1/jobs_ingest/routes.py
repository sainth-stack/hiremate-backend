"""
Internal ingestion routes (scheduler / ops). Auth: `X-Ingest-Secret` header.

Response counters: `total_inserted` matches `inserted` for a run; `total_filtered` matches
`filtered_out` (title_filter drops). See plan.md.
"""
from typing import Any
import asyncio
import threading

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_db
from backend.app.core.logging_config import get_logger
from backend.app.db.session import get_db_context
from backend.app.services.jobscrapping import (
    run_career_pages_ingestion,
    run_public_urls_ingestion,
    run_unified_companies_ingestion,
)
from backend.app.services.jobscrapping.public_apis import run_public_apis_ingestion_with_run_record
from backend.app.services.jobscrapping.ingest_lock import ingest_route_lock

logger = get_logger("jobs_ingest_routes")

router = APIRouter(prefix="/jobs", tags=["jobs-ingest"])
_public_apis_state_lock = threading.Lock()
_public_apis_running = False


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


def _lock_public_apis():
    with ingest_route_lock("public-apis"):
        yield


async def _run_background_ingestion(dry_run: bool):
    """Background task to run job ingestion."""
    global _public_apis_running
    try:
        with ingest_route_lock("public-apis"):
            logger.info("🚀 Starting background job ingestion...")
            with get_db_context() as db:
                m = await run_public_apis_ingestion_with_run_record(db, dry_run=dry_run)
            logger.info(
                f"✅ Background ingestion completed: "
                f"inserted={m.inserted}, updated={m.updated}, "
                f"skipped={m.skipped}, errors={m.errors}"
            )
    except Exception as e:
        logger.error(f"❌ Background ingestion failed: {e}", exc_info=True)
    finally:
        with _public_apis_state_lock:
            _public_apis_running = False


def _start_public_apis_thread(dry_run: bool) -> bool:
    """
    Start ingestion in a dedicated daemon thread so API requests stay responsive.
    Returns False if a run is already in progress in this process.
    """
    global _public_apis_running
    with _public_apis_state_lock:
        if _public_apis_running:
            return False
        _public_apis_running = True

    thread = threading.Thread(
        target=lambda: asyncio.run(_run_background_ingestion(dry_run)),
        name="public-apis-ingestion",
        daemon=True,
    )
    thread.start()
    return True


@router.post("/ingest/public-apis")
async def ingest_from_public_apis(
    body: IngestBody,
    _: Session = Depends(get_db),
    __: None = Depends(verify_ingest_secret),
) -> dict[str, Any]:
    """
    Ingest jobs from public APIs (RemoteOK, Remotive, Greenhouse, LinkedIn, etc).
    Runs in the background and returns immediately.
    Fetches 400-800+ jobs from ALL companies automatically.
    """
    started = _start_public_apis_thread(body.dry_run)
    if not started:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Public APIs ingestion is already running. Retry later.",
        )
    
    return {
        "status": "started",
        "message": "Job ingestion started in detached background thread. Check logs for progress.",
        "dry_run": body.dry_run,
        "sources": [
            "RemoteOK (Universal)",
            "Remotive (Universal)",
            "Arbeitnow (Aggregator)",
            "Greenhouse (Auto-discovery)",
            "LinkedIn (US + India)"
        ],
        "expected_jobs": "400-800+ jobs from ALL companies"
    }
