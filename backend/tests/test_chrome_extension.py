"""Tests for GET /api/chrome-extension/autofill/context and POST /api/chrome-extension/cover-letter/upsert"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# --- Autofill context ---


def test_autofill_context_requires_auth(client):
    """Auth required: assert 401 without token."""
    r = client.get("/api/chrome-extension/autofill/context")
    assert r.status_code == 401


def test_autofill_context_returns_200(client, auth_headers, test_user):
    """Returns 200 with keys: profile, resume_text, resume_url, custom_answers."""
    r = client.get("/api/chrome-extension/autofill/context", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "profile" in data
    assert "resume_text" in data
    assert "resume_url" in data
    assert "custom_answers" in data


def test_autofill_context_resume_url_type(client, auth_headers, test_user):
    """resume_url is string or null (not missing)."""
    r = client.get("/api/chrome-extension/autofill/context", headers=auth_headers)
    data = r.json()
    assert "resume_url" in data
    assert data["resume_url"] is None or isinstance(data["resume_url"], str)


def test_autofill_context_cache_second_call(client, auth_headers, test_user):
    """Cache test: when cache.get returns a value, DB/ProfileService is not queried."""
    import backend.app.utils.cache as cache_module
    from backend.app.services import profile_service

    r0 = client.get("/api/chrome-extension/autofill/context", headers=auth_headers)
    assert r0.status_code == 200
    cached = dict(r0.json())

    get_or_create_mock = MagicMock(wraps=profile_service.ProfileService.get_or_create_profile)

    async def mock_get_always_hit(_key):
        return cached

    with patch.object(profile_service.ProfileService, "get_or_create_profile", get_or_create_mock):
        with patch.object(cache_module, "get", new_callable=AsyncMock, side_effect=mock_get_always_hit):
            with patch.object(cache_module, "set", new_callable=AsyncMock):
                r = client.get("/api/chrome-extension/autofill/context", headers=auth_headers)
                assert r.status_code == 200
                assert r.json() == r0.json()
                # Cache hit: get_or_create_profile must not be called
                assert get_or_create_mock.call_count == 0


# --- Cover letter upsert ---


def test_cover_letter_upsert_requires_auth(client):
    """Auth required: assert 401 without token."""
    r = client.post(
        "/api/chrome-extension/cover-letter/upsert",
        json={"job_url": "https://example.com/job/1", "page_html": "", "job_title": "Engineer"},
    )
    assert r.status_code == 401


def test_cover_letter_upsert_first_call_returns_content(client, auth_headers, test_user):
    """First call with new job_url: returns 200, response has cover letter content."""
    with patch("backend.app.services.cover_letter_service.generate_cover_letter") as mock_gen:
        mock_gen.return_value = "Dear Hiring Manager,\n\nI am excited to apply..."
        r = client.post(
            "/api/chrome-extension/cover-letter/upsert",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={
                "job_url": "https://example.com/job/1",
                "page_html": "Job description here " * 20,
                "job_title": "Software Engineer",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "content" in data
        assert "job_title" in data
        assert mock_gen.call_count == 1


def test_cover_letter_upsert_same_job_url_no_second_llm_call(client, auth_headers, test_user):
    """Second call with SAME job_url: returns 200, same content, LLM was NOT called again."""
    with patch("backend.app.services.cover_letter_service.generate_cover_letter") as mock_gen:
        mock_gen.return_value = "Dear Hiring Manager,\n\nI am excited..."
        job_url = "https://example.com/job/same"
        payload = {
            "job_url": job_url,
            "page_html": "Job description " * 20,
            "job_title": "Engineer",
        }
        r1 = client.post(
            "/api/chrome-extension/cover-letter/upsert",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=payload,
        )
        assert r1.status_code == 200
        content1 = r1.json()["content"]

        r2 = client.post(
            "/api/chrome-extension/cover-letter/upsert",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=payload,
        )
        assert r2.status_code == 200
        assert r2.json()["content"] == content1
        assert mock_gen.call_count == 1


def test_cover_letter_upsert_different_job_url_calls_llm_again(client, auth_headers, test_user):
    """Call with different job_url: LLM IS called again (call_count == 2 total)."""
    with patch("backend.app.services.cover_letter_service.generate_cover_letter") as mock_gen:
        mock_gen.return_value = "Dear Hiring Manager..."
        r1 = client.post(
            "/api/chrome-extension/cover-letter/upsert",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={"job_url": "https://example.com/job/1", "page_html": "x" * 150, "job_title": "A"},
        )
        assert r1.status_code == 200
        assert mock_gen.call_count == 1

        r2 = client.post(
            "/api/chrome-extension/cover-letter/upsert",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={"job_url": "https://example.com/job/2", "page_html": "y" * 150, "job_title": "B"},
        )
        assert r2.status_code == 200
        assert mock_gen.call_count == 2
