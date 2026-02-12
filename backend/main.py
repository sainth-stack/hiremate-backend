"""
FastAPI application entry point
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.chrome_extension.routes import router as chrome_extension_router
from backend.app.api.v1.user.profile import router as profile_router
from backend.app.api.v1.user.resume import router as resume_router
from backend.app.core.logging_config import setup_logging
from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger
from sqlalchemy import text
from backend.app.db.session import engine
# Import models so they register with Base.metadata (for migrations)
import backend.app.models  # noqa: F401

logger = get_logger("main")
setup_logging()

# Initialize FastAPI app
app = FastAPI(
    title="JobSeeker API",
    description="Job seeking application API",
    version="1.0.0"
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
app.include_router(resume_router, prefix="/api/resume", tags=["resume"])
app.include_router(profile_router, prefix="/api/profile", tags=["profile"])
app.include_router(chrome_extension_router, prefix="/api")

# Serve uploaded resumes (create dir if missing)
upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount(f"/{settings.upload_dir}", StaticFiles(directory=settings.upload_dir), name="resumes")


@app.on_event("startup")
def verify_db_connection():
    """Verify database connection on startup. Fail fast if credentials are wrong."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as e:
        logger.error("Database connection failed at startup: %s", str(e))
        raise RuntimeError(
            f"Database connection failed. Check DATABASE_URL in .env. Error: {e}"
        ) from e


@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "JobSeeker API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5432)
