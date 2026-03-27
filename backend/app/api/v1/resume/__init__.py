"""
Resume API package - aggregates user resume routes and ATS scan / analyze endpoints.
All resume-related APIs are mounted under /api/resume.
"""
from fastapi import APIRouter

from backend.app.api.v1.user.resume import router as user_resume_router
from backend.app.api.v1.user.preferences import router as preferences_router

from .ats_scan import router as ats_scan_router
from .analyze import router as analyze_router

router = APIRouter()
router.include_router(user_resume_router)
router.include_router(preferences_router)
router.include_router(ats_scan_router, tags=["ats-scan"])
router.include_router(analyze_router, tags=["resume-analyze"])
