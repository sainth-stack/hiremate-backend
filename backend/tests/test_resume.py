"""Tests for GET /api/resume/workspace"""
import pytest

from backend.app.services.tailor_context_store import set_tailor_context


def test_resume_workspace_requires_auth(client):
    """Auth required: assert 401 without token."""
    r = client.get("/api/resume/workspace")
    assert r.status_code == 401


def test_resume_workspace_returns_200(client, auth_headers):
    """Returns 200 with keys: resumes, tailor_context."""
    r = client.get("/api/resume/workspace", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "resumes" in data
    assert "tailor_context" in data


def test_resume_workspace_resumes_is_list(client, auth_headers):
    """resumes is a list."""
    r = client.get("/api/resume/workspace", headers=auth_headers)
    data = r.json()
    assert isinstance(data["resumes"], list)


def test_resume_workspace_tailor_context_null_when_empty(client, auth_headers):
    """tailor_context is null when nothing stored."""
    r = client.get("/api/resume/workspace", headers=auth_headers)
    data = r.json()
    assert data["tailor_context"] is None


def test_resume_workspace_tailor_context_when_stored(client, auth_headers, test_user):
    """tailor_context has job_title and job_description when something was stored."""
    set_tailor_context(
        test_user.id,
        job_description="Build scalable systems.",
        job_title="Senior Engineer",
    )
    r = client.get("/api/resume/workspace", headers=auth_headers)
    data = r.json()
    assert data["tailor_context"] is not None
    assert data["tailor_context"]["job_title"] == "Senior Engineer"
    assert data["tailor_context"]["job_description"] == "Build scalable systems."


def test_resume_workspace_fetch_and_clear(client, auth_headers, test_user):
    """After fetching when tailor_context exists: second fetch returns tailor_context as null."""
    set_tailor_context(test_user.id, job_description="JD here", job_title="Dev")
    r1 = client.get("/api/resume/workspace", headers=auth_headers)
    assert r1.json()["tailor_context"] is not None

    r2 = client.get("/api/resume/workspace", headers=auth_headers)
    assert r2.json()["tailor_context"] is None
