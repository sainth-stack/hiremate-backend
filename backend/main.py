"""
FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.v1 import auth
from backend.app.db.base import Base
from backend.app.db.session import engine

# Create database tables
try:
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
