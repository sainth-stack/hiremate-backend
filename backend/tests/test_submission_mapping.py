"""Tests for submit_feedback mapping analysis and admin submission log endpoints."""
import pytest


# --- Submit feedback mapping analysis ---

def test_submit_feedback_requires_auth(client):
    """Auth required: assert 401 without token."""
    r = client.post("/api/chrome-extension/form-fields/submit-feedback", json={
        "url": "https://example.com/apply",
        "domain": "example.com",
        "fields": [],
    })
    assert r.status_code == 401


def test_submit_feedback_stores_mapping_analysis(client, auth_headers, test_user):
    """submit_feedback computes and stores mapping_analysis with correct metrics."""
    payload = {
        "url": "https://greenhouse.io/company/job/123",
        "domain": "greenhouse.io",
        "ats": "greenhouse",
        "fields": [
            {
                "fingerprint": "fp_name_001",
                "label": "Full Name",
                "type": "text",
                "autofill_value": "Sainath Reddy",
                "submitted_value": "Sainath Reddy",
                "was_edited": False,
            },
            {
                "fingerprint": "fp_email_002",
                "label": "Email",
                "type": "email",
                "autofill_value": "sainath@example.com",
                "submitted_value": "different@example.com",
                "was_edited": True,
            },
            {
                "fingerprint": "fp_phone_003",
                "label": "Phone",
                "type": "tel",
                "autofill_value": None,
                "submitted_value": None,
                "was_edited": False,
            },
        ],
    }
    r = client.post(
        "/api/chrome-extension/form-fields/submit-feedback",
        headers={**auth_headers, "Content-Type": "application/json"},
        json=payload,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["learned"] == 2  # fp_phone_003 has no value, so only 2 learned

    # Check mapping_analysis in response
    analysis = data.get("mapping_analysis")
    assert analysis is not None
    assert analysis["total_fields"] == 3
    assert analysis["correctly_mapped"] == 1  # Full Name
    assert analysis["user_changed"] == 1  # Email
    assert analysis["unmapped"] == 1  # Phone
    assert analysis["accuracy_pct"] == 50.0  # 1 out of 2 with values


def test_submit_feedback_all_matched(client, auth_headers, test_user):
    """All fields matched correctly: accuracy 100%."""
    payload = {
        "url": "https://lever.co/job/apply",
        "domain": "lever.co",
        "ats": "lever",
        "fields": [
            {
                "fingerprint": "fp_name_100",
                "label": "Name",
                "type": "text",
                "autofill_value": "Test User",
                "submitted_value": "Test User",
                "was_edited": False,
            },
            {
                "fingerprint": "fp_email_100",
                "label": "Email",
                "type": "email",
                "autofill_value": "test@example.com",
                "submitted_value": "test@example.com",
                "was_edited": False,
            },
        ],
    }
    r = client.post(
        "/api/chrome-extension/form-fields/submit-feedback",
        headers={**auth_headers, "Content-Type": "application/json"},
        json=payload,
    )
    assert r.status_code == 200
    analysis = r.json()["mapping_analysis"]
    assert analysis["correctly_mapped"] == 2
    assert analysis["user_changed"] == 0
    assert analysis["unmapped"] == 0
    assert analysis["accuracy_pct"] == 100.0


# --- Admin submission logs ---


def test_admin_submission_logs_requires_admin(client, auth_headers, test_user):
    """Non-admin user gets 403."""
    r = client.get("/api/admin/learning/submission-logs", headers=auth_headers)
    assert r.status_code == 403


def test_admin_submission_logs_returns_list(client, auth_headers, admin_headers, test_user, admin_user):
    """Admin can list submission logs after a submission is created."""
    # Create a submission first
    client.post(
        "/api/chrome-extension/form-fields/submit-feedback",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={
            "url": "https://example.com/apply",
            "domain": "example.com",
            "ats": "unknown",
            "fields": [
                {
                    "fingerprint": "fp_test_200",
                    "label": "Name",
                    "type": "text",
                    "autofill_value": "Test",
                    "submitted_value": "Test",
                    "was_edited": False,
                },
            ],
        },
    )

    # Admin queries submission logs
    r = client.get(
        "/api/admin/learning/submission-logs",
        headers=admin_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "submissions" in data
    assert "total" in data
    assert data["total"] >= 1
    sub = data["submissions"][0]
    assert "id" in sub
    assert "email" in sub
    assert "domain" in sub
    assert "accuracy_pct" in sub
    assert "correctly_mapped" in sub


def test_admin_submission_log_detail(client, auth_headers, admin_headers, test_user, admin_user):
    """Admin can fetch individual submission detail with field-level data."""
    # Create submission
    r_sub = client.post(
        "/api/chrome-extension/form-fields/submit-feedback",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={
            "url": "https://greenhouse.io/job/1",
            "domain": "greenhouse.io",
            "ats": "greenhouse",
            "fields": [
                {
                    "fingerprint": "fp_det_300",
                    "label": "First Name",
                    "type": "text",
                    "autofill_value": "Test",
                    "submitted_value": "Test",
                    "was_edited": False,
                },
                {
                    "fingerprint": "fp_det_301",
                    "label": "Last Name",
                    "type": "text",
                    "autofill_value": "User",
                    "submitted_value": "Modified",
                    "was_edited": True,
                },
            ],
        },
    )
    assert r_sub.status_code == 200

    # Get the submission list to find the ID
    r_list = client.get("/api/admin/learning/submission-logs", headers=admin_headers)
    assert r_list.status_code == 200
    subs = r_list.json()["submissions"]
    assert len(subs) >= 1
    sub_id = subs[0]["id"]

    # Fetch detail
    r_detail = client.get(f"/api/admin/learning/submission-logs/{sub_id}", headers=admin_headers)
    assert r_detail.status_code == 200
    detail = r_detail.json()
    assert detail["id"] == sub_id
    assert detail["domain"] == "greenhouse.io"
    assert isinstance(detail["submitted_fields"], list)
    assert len(detail["submitted_fields"]) == 2
    assert isinstance(detail["mapping_analysis"], dict)
    assert detail["mapping_analysis"]["correctly_mapped"] == 1
    assert detail["mapping_analysis"]["user_changed"] == 1

    # Check field-level data
    fields = detail["submitted_fields"]
    first_name_field = next(f for f in fields if f["label"] == "First Name")
    assert first_name_field["autofill_value"] == "Test"
    assert first_name_field["submitted_value"] == "Test"
    assert first_name_field["was_edited"] is False

    last_name_field = next(f for f in fields if f["label"] == "Last Name")
    assert last_name_field["autofill_value"] == "User"
    assert last_name_field["submitted_value"] == "Modified"
    assert last_name_field["was_edited"] is True


def test_admin_submission_log_detail_not_found(client, admin_headers, admin_user):
    """Returns 404 for non-existent submission."""
    r = client.get("/api/admin/learning/submission-logs/99999", headers=admin_headers)
    assert r.status_code == 404
