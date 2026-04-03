"""
FastAPI application entry point
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.api.v1.activity import router as activity_router
from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.chrome_extension.routes import router as chrome_extension_router
from backend.app.api.v1.dashboard import router as dashboard_router
from backend.app.api.v1.legal import router as legal_router
from backend.app.api.v1.company_search.routes import router as company_search_router
from backend.app.api.v1.issues import router as issues_router
from backend.app.api.v1.payment import router as payment_router
from backend.app.api.v1.user.profile import router as profile_router
from backend.app.api.v1.resume import router as resume_router
from backend.app.core.logging_config import setup_logging
from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from backend.jobradar.api.applications import router as applications_router
from backend.jobradar.api.sync import router as sync_router
from backend.jobradar.api.chat import router as chat_router
from backend.jobradar.api.webhooks import router as webhooks_router
# from jobradar.api.nudges import router as nudges_router
from backend.jobradar.api.insights import router as insights_router
from sqlalchemy import text
from backend.app.db.session import engine
# Import models so they register with Base.metadata (for migrations)
import backend.app.models  # noqa: F401

logger = get_logger("main")
setup_logging()


def _advance_history_ids_on_startup():
    """
    On startup, fast-forward every user's last_history_id to their current
    Gmail mailbox cursor. This causes the stale-push guard in sentinel.py to
    silently drop all notifications that were queued while the server was down,
    so we don't replay days of old emails. Users can run a manual sync instead.
    """
    from backend.app.db.session import SessionLocal
    from backend.app.models.user import User
    from backend.app.services.google_oauth import get_credentials_for_user
    from backend.jobradar.services.gmail_service import get_latest_history_id

    db = SessionLocal()
    try:
        users = db.query(User).filter(User.last_history_id.isnot(None)).all()
        logger.info("STARTUP: Advancing last_history_id for %d user(s)...", len(users))
        for user in users:
            try:
                creds = get_credentials_for_user(db, user)
                latest = get_latest_history_id(creds)
                if latest and int(latest) > int(user.last_history_id):
                    logger.info(
                        "STARTUP: %s → history %s → %s (skipping queued pushes)",
                        user.email, user.last_history_id, latest,
                    )
                    user.last_history_id = str(latest)
            except Exception as e:
                logger.warning("STARTUP: Could not advance history_id for %s: %s", user.email, e)
        db.commit()
    except Exception as e:
        logger.error("STARTUP: Failed to advance history IDs: %s", e)
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: verify DB + start scheduler. Shutdown: stop scheduler."""
    # Verify database connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as e:
        logger.error("Database connection failed at startup: %s", str(e))
        raise RuntimeError(
            f"Database connection failed. Check DATABASE_URL in .env. Error: {e}"
        ) from e

    # Advance Gmail history cursors so queued Pub/Sub notifications from downtime are ignored
    _advance_history_ids_on_startup()

    # Start background scheduler
    # from jobradar.scheduler import start_scheduler
    # start_scheduler()

    yield

    # Shutdown
    # from jobradar.scheduler import stop_scheduler
    # stop_scheduler()


# Initialize FastAPI app
app = FastAPI(
    title="HireMate API",
    description="Job seeking application API",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(payment_router, prefix="/api/payment", tags=["payment"])
app.include_router(resume_router, prefix="/api/resume", tags=["resume"])
app.include_router(profile_router, prefix="/api/profile", tags=["profile"])
app.include_router(dashboard_router, prefix="/api")
app.include_router(chrome_extension_router, prefix="/api")
app.include_router(activity_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(legal_router, prefix="/api", tags=["legal"])
app.include_router(issues_router, prefix="/api", tags=["issues"])
app.include_router(company_search_router, prefix="/api")
app.include_router(applications_router, prefix="/api/applications", tags=["applications"])
app.include_router(sync_router, prefix="/api/sync", tags=["sync"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])
# app.include_router(nudges_router, prefix="/api/nudges", tags=["nudges"])
app.include_router(insights_router, prefix="/api/insights", tags=["insights"])

# Serve uploaded resumes (create dir if missing)
upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount(f"/{settings.upload_dir}", StaticFiles(directory=settings.upload_dir), name="resumes")


@app.on_event("startup")
async def on_startup():
    """Verify database connection and connect Redis cache on startup."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as e:
        logger.error("Database connection failed at startup: %s", str(e))
        raise RuntimeError(
            f"Database connection failed. Check DATABASE_URL in .env. Error: {e}"
        ) from e

    from backend.app.utils import cache
    await cache.connect()

    # Seed default privacy policy if the table is empty
    try:
        from backend.app.db.session import SessionLocal
        from backend.app.services.legal_service import LegalService
        with SessionLocal() as db:
            LegalService.seed_default_privacy_policy(db)
    except Exception as e:
        logger.warning("Could not seed privacy policy: %s", str(e))


@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "HireMate API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
