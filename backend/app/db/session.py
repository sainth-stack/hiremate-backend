"""
Database session configuration
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.config import settings

engine = create_engine(
    settings.database_url,
    echo=False,
    # Test each connection before handing it to a request.
    # Catches stale/closed connections (e.g. RDS idle timeout) and transparently
    # replaces them, eliminating the "server closed the connection unexpectedly" error.
    pool_pre_ping=True,
    # Recycle connections older than 30 minutes regardless of health.
    # RDS default idle timeout is typically 5-8 hours, but this keeps the pool fresh.
    pool_recycle=1800,
    # Max connections in the pool. Default is 5 — raise for concurrent load.
    pool_size=10,
    # Allow up to 5 extra connections beyond pool_size under burst load.
    max_overflow=5,
    # Wait up to 30s for a connection before raising an error.
    pool_timeout=30,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
