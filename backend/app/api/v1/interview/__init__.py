from backend.app.api.v1.interview.routes import router
from backend.app.api.v1.interview.voice_routes import router as voice_router

router.include_router(voice_router)

__all__ = ["router"]
