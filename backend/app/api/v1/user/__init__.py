"""User API module - profile and resume endpoints."""
from backend.app.api.v1.user.profile import router as profile_router
from backend.app.api.v1.user.resume import router as resume_router

__all__ = ["profile_router", "resume_router"]
