"""Tests for GET /api/dashboard/summary"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def test_dashboard_summary_requires_auth(client):
    """Auth required: assert 401 without token."""
    r = client.get("/api/dashboard/summary")
    assert r.status_code == 401


def test_dashboard_summary_returns_200(client, auth_headers):
    """Returns 200 with authenticated user."""
    r = client.get("/api/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200


def test_dashboard_summary_response_shape(client, auth_headers):
    """Response has all keys: stats, recent_applications, companies_viewed, applications_by_day."""
    r = client.get("/api/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "stats" in data
    assert "recent_applications" in data
    assert "companies_viewed" in data
    assert "applications_by_day" in data


def test_dashboard_summary_stats_keys(client, auth_headers):
    """stats has keys: jobs_applied, jobs_saved, companies_checked (all int)."""
    r = client.get("/api/dashboard/summary", headers=auth_headers)
    data = r.json()
    stats = data["stats"]
    assert "jobs_applied" in stats
    assert "jobs_saved" in stats
    assert "companies_checked" in stats
    assert isinstance(stats["jobs_applied"], int)
    assert isinstance(stats["jobs_saved"], int)
    assert isinstance(stats["companies_checked"], int)


def test_dashboard_summary_lists(client, auth_headers):
    """recent_applications and companies_viewed are lists; applications_by_day is a list."""
    r = client.get("/api/dashboard/summary", headers=auth_headers)
    data = r.json()
    assert isinstance(data["recent_applications"], list)
    assert isinstance(data["companies_viewed"], list)
    assert isinstance(data["applications_by_day"], list)


def test_dashboard_summary_limit_and_days_params(client, auth_headers):
    """Test with ?limit=3&days=3: lists respect the limit param."""
    r = client.get("/api/dashboard/summary", params={"limit": 3, "days": 3}, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["recent_applications"]) <= 3
    assert len(data["companies_viewed"]) <= 3
    # applications_by_day may have 0-3 entries depending on data
    assert all(isinstance(d, dict) and "date" in d and "count" in d for d in data["applications_by_day"])


def test_dashboard_summary_cache_second_call_uses_cache(client, auth_headers):
    """Cache test: call twice, mock Redis.get to return value on second call, assert DB query only ran once."""
    from backend.app.api.v1.dashboard import routes as dashboard_routes

    build_mock = MagicMock(wraps=dashboard_routes._build_dashboard_summary)

    with patch.object(dashboard_routes, "_build_dashboard_summary", build_mock), \
         patch("backend.app.utils.cache.get", new_callable=AsyncMock) as mock_get, \
         patch("backend.app.utils.cache.set", new_callable=AsyncMock) as mock_set:
        # First call: cache miss (get returns None)
        mock_get.return_value = None
        r1 = client.get("/api/dashboard/summary", headers=auth_headers)
        assert r1.status_code == 200
        first_data = r1.json()

        # Second call: cache hit (get returns cached data)
        mock_get.return_value = first_data
        r2 = client.get("/api/dashboard/summary", headers=auth_headers)
        assert r2.status_code == 200
        assert r2.json() == first_data

        # _build_dashboard_summary (DB query) was called only once
        assert build_mock.call_count == 1
