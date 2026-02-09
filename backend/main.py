"""
FastAPI application entry point
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.api.v1 import auth, profile, resume
from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.session import engine

# Import models so they register with Base.metadata
import backend.app.models  # noqa: F401

from sqlalchemy import text, inspect

# Create database tables
try:
    # Fix outdated profiles table (missing resume_url etc.)
    with engine.connect() as conn:
        if engine.dialect.has_table(conn, "profiles"):
            insp = inspect(engine)
            cols = [c["name"] for c in insp.get_columns("profiles")]
            if "resume_url" not in cols:
                conn.execute(text("DROP TABLE profiles"))
                conn.commit()
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Database error: {e}")

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
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(resume.router, prefix="/api/resume", tags=["resume"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])

# Serve uploaded resumes (create dir if missing)
upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount(f"/{settings.upload_dir}", StaticFiles(directory=settings.upload_dir), name="resumes")


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
