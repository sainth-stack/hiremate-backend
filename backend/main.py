"""
FastAPI application entry point
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.api.v1.activity import router as activity_router
from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.admin.plans import router as admin_plans_router
from backend.app.api.v1.admin.interviews import router as admin_interviews_router
from backend.app.api.v1.admin.interview_requests import router as admin_interview_requests_router
from backend.app.api.v1.launched_interviews import router as launched_interviews_router
from backend.app.api.v1.interview import router as live_interview_router
from backend.app.api.v1.interview_requests import router as interview_requests_router
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
from backend.jobradar.api.mock_interview import router as mock_interview_router
from backend.jobradar.api.briefing import router as briefing_router
from backend.jobradar.api.insights import router as insights_router
from backend.app.api.v1.jobs_ingest import router as jobs_ingest_router
from sqlalchemy import text
from backend.app.db.session import engine
from backend.app.core.dependencies import check_token_balance
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


def _ensure_interviews_table():
    """Create interview-related tables if missing (handles out-of-sync Alembic state)."""
    from sqlalchemy import inspect

    from backend.app.models.interview import Interview
    from backend.app.models.interview_question import InterviewQuestion
    from backend.app.models.interview_request import InterviewRequest
    from backend.app.models.launched_interview import LaunchedInterview, LaunchedInterviewUser

    if not inspect(engine).has_table("interviews"):
        Interview.__table__.create(bind=engine, checkfirst=True)
        logger.info("STARTUP: Created missing interviews table")
    else:
        _ensure_interview_voice_columns()
    if not inspect(engine).has_table("interview_questions"):
        InterviewQuestion.__table__.create(bind=engine, checkfirst=True)
        logger.info("STARTUP: Created missing interview_questions table")
    if not inspect(engine).has_table("interview_requests"):
        InterviewRequest.__table__.create(bind=engine, checkfirst=True)
        logger.info("STARTUP: Created missing interview_requests table")
    if not inspect(engine).has_table("launched_interviews"):
        LaunchedInterview.__table__.create(bind=engine, checkfirst=True)
        logger.info("STARTUP: Created missing launched_interviews table")
    else:
        _ensure_launched_interview_columns()
        _ensure_launched_interview_voice_columns()
    if not inspect(engine).has_table("launched_interview_users"):
        LaunchedInterviewUser.__table__.create(bind=engine, checkfirst=True)
        logger.info("STARTUP: Created missing launched_interview_users table")
    else:
        _ensure_launched_interview_user_columns()


def _ensure_interview_voice_columns():
    """Add voice settings columns to interviews if missing."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if not inspector.has_table("interviews"):
        return
    existing = {col["name"] for col in inspector.get_columns("interviews")}
    alters = []
    if "tts_speaker" not in existing:
        alters.append("ALTER TABLE interviews ADD COLUMN tts_speaker VARCHAR(64) NULL")
    if "tts_language_code" not in existing:
        alters.append("ALTER TABLE interviews ADD COLUMN tts_language_code VARCHAR(16) NULL")
    if "question_count" not in existing:
        alters.append("ALTER TABLE interviews ADD COLUMN question_count INTEGER NOT NULL DEFAULT 15")
    if not alters:
        return
    with engine.begin() as conn:
        for stmt in alters:
            conn.execute(text(stmt))
    logger.info("STARTUP: Added interview voice columns")


def _ensure_launched_interview_user_columns():
    """Add submit-tracking columns if missing (handles out-of-sync Alembic state)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if not inspector.has_table("launched_interview_users"):
        return
    existing = {col["name"] for col in inspector.get_columns("launched_interview_users")}
    alters = []
    if "status" not in existing:
        alters.append(
            "ALTER TABLE launched_interview_users "
            "ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'"
        )
    if "submitted_at" not in existing:
        alters.append(
            "ALTER TABLE launched_interview_users ADD COLUMN submitted_at TIMESTAMP NULL"
        )
    if "submission_data" not in existing:
        alters.append(
            "ALTER TABLE launched_interview_users ADD COLUMN submission_data JSON NULL"
        )
    if not alters:
        return
    with engine.begin() as conn:
        for stmt in alters:
            conn.execute(text(stmt))
    logger.info("STARTUP: Added missing launched_interview_users columns")


def _ensure_launched_interview_columns():
    """Add launch_name column if missing."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if not inspector.has_table("launched_interviews"):
        return
    existing = {col["name"] for col in inspector.get_columns("launched_interviews")}
    if "launch_name" in existing:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE launched_interviews ADD COLUMN launch_name VARCHAR(255) NULL"))
    logger.info("STARTUP: Added launch_name to launched_interviews")


def _ensure_launched_interview_voice_columns():
    """Add voice settings columns to launched_interviews if missing."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if not inspector.has_table("launched_interviews"):
        return
    existing = {col["name"] for col in inspector.get_columns("launched_interviews")}
    alters = []
    if "voice_provider" not in existing:
        alters.append("ALTER TABLE launched_interviews ADD COLUMN voice_provider VARCHAR(32) NULL")
    if "voice_id" not in existing:
        alters.append("ALTER TABLE launched_interviews ADD COLUMN voice_id VARCHAR(128) NULL")
    if "voice_label" not in existing:
        alters.append("ALTER TABLE launched_interviews ADD COLUMN voice_label VARCHAR(255) NULL")
    if "tts_language_code" not in existing:
        alters.append("ALTER TABLE launched_interviews ADD COLUMN tts_language_code VARCHAR(16) NULL")
    if "question_count" not in existing:
        alters.append("ALTER TABLE launched_interviews ADD COLUMN question_count INTEGER NULL")
    if not alters:
        return
    with engine.begin() as conn:
        for stmt in alters:
            conn.execute(text(stmt))
    logger.info("STARTUP: Added launched_interviews voice columns")


def _seed_subscription_plans():
    """Upsert default subscription plans on every startup."""
    from backend.app.db.session import SessionLocal
    from backend.app.models.subscription_plan import SubscriptionPlan
    db = SessionLocal()
    defaults = [
        dict(
            id="free",
            name="Free",
            description="Basic plan for individuals",
            amount=0,
            monthly_tokens=25000,
            is_featured=False,
            features=[
                "25,000 AI Tokens / month",
                "Basic Design Templates",
                "Email Support",
            ],
        ),
        dict(
            id="pro",
            name="Pro",
            description="Professional plan for serious job seekers",
            amount=49900,  # ₹499
            monthly_tokens=500000,
            is_featured=True,
            features=[
                "500,000 AI Tokens / month",
                "Premium Design Kit",
                "Chrome Extension Access",
                "Priority Email Support",
            ],
        ),
        dict(
            id="elite",
            name="Elite",
            description="The ultimate plan for maximum success",
            amount=99900,  # ₹999
            monthly_tokens=-1,  # Unlimited
            is_featured=False,
            features=[
                "Unlimited AI Tokens",
                "AI Mock Interviews",
                "Priority AI Processing",
                "24/7 Priority Support",
            ],
        ),
    ]
    try:
        for plan_data in defaults:
            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_data["id"]).first()
            if plan is None:
                db.add(SubscriptionPlan(**plan_data))
                logger.info("STARTUP: Created plan %s", plan_data["id"])
            else:
                # Only patch fields that should be authoritative from code
                plan.is_featured = plan_data["is_featured"]
                plan.is_active = True
        db.commit()
        logger.info("STARTUP: Subscription plans upserted (%d plans)", len(defaults))
    except Exception as e:
        logger.warning("Could not seed subscription plans: %s", str(e))
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
        logger.info("STARTUP: FRONTEND_URL=%s", settings.frontend_url)
    except Exception as e:
        logger.error("Database connection failed at startup: %s", str(e))
        raise RuntimeError(
            f"Database connection failed. Check DATABASE_URL in .env. Error: {e}"
        ) from e

    from backend.app.services.jobscrapping.ingest_lock import clear_stale_ingest_locks_on_startup
    from backend.app.scheduler.job_ingestion import start_scheduler, stop_scheduler

    clear_stale_ingest_locks_on_startup()

    _ensure_interviews_table()
    _seed_subscription_plans()

    # Advance Gmail history cursors so queued Pub/Sub notifications from downtime are ignored
    _advance_history_ids_on_startup()

    # Optional in-process scheduler (disabled when Celery beat handles ingestion)
    start_scheduler()
    if settings.enable_in_process_scheduler:
        logger.info("In-process job ingestion scheduler started")
    else:
        logger.info(
            "API-only mode for scheduled jobs — run Celery worker + beat (see ecosystem.config.cjs)"
        )

    yield

    # Shutdown
    stop_scheduler()
    logger.info("Scheduler stopped")


# Initialize FastAPI app
app = FastAPI(
    title="OpsBrain API",
    description="AI-powered job search platform API",
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
    expose_headers=["X-Token-Balance", "X-Token-Low-Balance"],
)

# 1. Public / Administrative Routers (No token check required)
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(payment_router, prefix="/api/payment", tags=["payment"])
app.include_router(legal_router, prefix="/api", tags=["legal"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])

# These were requested to be ignored from token limitations
app.include_router(dashboard_router, prefix="/api", tags=["dashboard"])
app.include_router(admin_router, prefix="/api", tags=["admin"])
app.include_router(admin_plans_router, prefix="/api/admin", tags=["admin"])
app.include_router(admin_interviews_router, prefix="/api/admin", tags=["admin"])
app.include_router(admin_interview_requests_router, prefix="/api/admin", tags=["admin"])
app.include_router(interview_requests_router, prefix="/api", tags=["interview-requests"])
app.include_router(launched_interviews_router, prefix="/api", tags=["launched-interviews"])
app.include_router(live_interview_router, prefix="/api/interview", tags=["interview"])
app.include_router(company_search_router, prefix="/api", tags=["research"])
app.include_router(activity_router, prefix="/api", tags=["activity"])
app.include_router(issues_router, prefix="/api", tags=["issues"])
app.include_router(jobs_ingest_router, prefix="/api/v1", tags=["jobs-ingest"])

# 2. Protected Routers (Apply global token + auth gate)
protected_api_routers = [
    (resume_router, "/api/resume", ["resume"]),
    (profile_router, "/api/profile", ["profile"]),
    (chrome_extension_router, "/api", ["extension"]),
    (applications_router, "/api/applications", ["applications"]),
    (sync_router, "/api/sync", ["sync"]),
    (chat_router, "/api/chat", ["chat"]),
    (mock_interview_router, "/api/mock-interview", ["mock-interview"]),
    (briefing_router, "/api/mock-interview", ["mock-interview"]),
    (insights_router, "/api/insights", ["insights"]),
]

for router, prefix, tags in protected_api_routers:
    app.include_router(
        router, 
        prefix=prefix, 
        tags=tags, 
        dependencies=[Depends(check_token_balance)]
    )

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

    _ensure_interviews_table()

    # Seed default legal policies if the table is empty
    try:
        from backend.app.db.session import SessionLocal
        from backend.app.services.legal_service import LegalService
        with SessionLocal() as db:
            LegalService.seed_default_privacy_policy(db)
            LegalService.seed_default_terms_of_service(db)
    except Exception as e:
        logger.warning("Could not seed legal policies: %s", str(e))

    # Seed subscription plans
    _seed_subscription_plans()



@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "OpsBrain API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
