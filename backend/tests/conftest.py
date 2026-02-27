"""
Pytest fixtures for HireMate API tests.
Uses in-memory SQLite, mocks Redis, provides test user and auth token.
"""
import os
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Use in-memory SQLite for tests - set before config/session load
# Must override any .env DATABASE_URL
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key"

from backend.app.db.base import Base
from backend.main import app
from backend.app.core.dependencies import get_db
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.models.user import User
from backend.app.models.profile import Profile

# In-memory SQLite for tests - StaticPool ensures all sessions share same DB
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Patch the session module so app uses our test engine
import backend.app.db.session as session_module
session_module.engine = engine
session_module.SessionLocal = TestingSessionLocal
# main.py imports engine directly; patch so startup uses our engine
import backend.main as main_module
main_module.engine = engine


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def db_session():
    """Create tables and a fresh DB session per test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    """Create a test user in the DB."""
    user = User(
        id=1,
        first_name="Test",
        last_name="User",
        email="test@example.com",
        hashed_password=get_password_hash("testpass123"),
        is_active=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_with_profile(db_session, test_user):
    """Create test user with minimal profile (for autofill/cover-letter tests)."""
    profile = Profile(
        user_id=test_user.id,
        first_name=test_user.first_name,
        last_name=test_user.last_name,
        email=test_user.email,
        preferences={},
    )
    db_session.add(profile)
    db_session.commit()
    return test_user


@pytest.fixture
def auth_headers(test_user):
    """Bearer token for test user."""
    token = create_access_token(data={"sub": str(test_user.id), "email": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(db_session, test_user):
    """TestClient with DB and test user pre-seeded."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis cache: get returns None (cache miss), set/delete no-op. Skip connect."""
    with patch("backend.app.utils.cache.get", new_callable=AsyncMock, return_value=None), \
         patch("backend.app.utils.cache.set", new_callable=AsyncMock), \
         patch("backend.app.utils.cache.delete", new_callable=AsyncMock), \
         patch("backend.app.utils.cache.connect", new_callable=AsyncMock):
        yield

