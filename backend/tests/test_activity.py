"""Tests for POST /api/activity/track"""
import pytest

from backend.app.models.career_page_visit import CareerPageVisit


def test_activity_track_requires_auth(client):
    """Auth required: assert 401 without token."""
    r = client.post(
        "/api/activity/track",
        json={"event_type": "career_page_view", "page_url": "https://example.com"},
    )
    assert r.status_code == 401


def test_activity_track_career_page_view(client, auth_headers, db_session, test_user):
    """event_type career_page_view: returns { ok: true }, verify DB record created."""
    r = client.post(
        "/api/activity/track",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"event_type": "career_page_view", "page_url": "https://acme.com/careers"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    rows = db_session.query(CareerPageVisit).filter(
        CareerPageVisit.user_id == test_user.id,
        CareerPageVisit.action_type == "page_view",
    ).all()
    assert len(rows) == 1
    assert rows[0].page_url == "https://acme.com/careers"


def test_activity_track_autofill_used(client, auth_headers, db_session, test_user):
    """event_type autofill_used: returns { ok: true }, verify DB record created."""
    r = client.post(
        "/api/activity/track",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"event_type": "autofill_used", "page_url": "https://jobs.example.com/apply/123"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    rows = db_session.query(CareerPageVisit).filter(
        CareerPageVisit.user_id == test_user.id,
        CareerPageVisit.action_type == "autofill_used",
    ).all()
    assert len(rows) == 1
    assert rows[0].page_url == "https://jobs.example.com/apply/123"


def test_activity_track_invalid_event_type(client, auth_headers):
    """Invalid event_type: returns 422."""
    r = client.post(
        "/api/activity/track",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"event_type": "invalid_type", "page_url": "https://example.com"},
    )
    assert r.status_code == 422
