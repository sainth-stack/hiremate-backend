"""
Tests for Gmail Pub/Sub pipeline:
  - Webhook endpoint (POST /api/webhooks/gmail/push)
  - Sentinel agent (process_push_notification)
"""
import base64
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from jobradar.models.application import Application, StatusHistory
from app.models.user import User
from jobradar.services.classifier import ClassifierOutput



# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_pubsub_payload(email: str = "test@example.com", history_id: str = "12345") -> dict:
    """Build a well-formed Pub/Sub push body as Google sends it."""
    data = base64.b64encode(
        json.dumps({"emailAddress": email, "historyId": history_id}).encode()
    ).decode()
    return {
        "message": {
            "data": data,
            "messageId": "msg-001",
            "publishTime": "2024-01-01T00:00:00Z",
        },
        "subscription": "projects/test-project/subscriptions/test-sub",
    }


def _classifier_output(**kwargs) -> ClassifierOutput:
    defaults = dict(
        is_job_related=True,
        company="Acme Corp",
        role="Software Engineer",
        platform="LinkedIn",
        status="applied",
        next_action="Wait for response",
        confidence=0.92,
        summary="Applied for SWE role",
        interview_process=None,
    )
    defaults.update(kwargs)
    return ClassifierOutput(**defaults)


def _fake_messages() -> list[dict]:
    return [
        {
            "id": "msg-abc",
            "subject": "Your application to Acme Corp",
            "from": "jobs@acme.com",
            "date": "Mon, 01 Jan 2024 10:00:00 +0000",
            "body": "Thank you for applying to Acme Corp for the Software Engineer role.",
        }
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Webhook endpoint tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookEndpoint:
    """Integration tests for POST /api/webhooks/gmail/push"""

    def test_valid_payload_returns_accepted(self, client):
        with patch("jobradar.services.sentinel.process_push_notification") as mock_sentinel:
            resp = client.post("/api/webhooks/gmail/push", json=_make_pubsub_payload())
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_sentinel_triggered_in_background(self, client):
        """Webhook must schedule sentinel as a background task (not block the response)."""
        with patch("jobradar.services.sentinel.process_push_notification") as mock_sentinel:
            resp = client.post("/api/webhooks/gmail/push", json=_make_pubsub_payload())
        assert resp.status_code == 200
        # TestClient runs background tasks synchronously — verify it was called
        mock_sentinel.assert_called_once_with("test@example.com", "12345")

    def test_missing_email_address_ignored(self, client):
        data = base64.b64encode(json.dumps({"historyId": "999"}).encode()).decode()
        payload = {
            "message": {"data": data, "messageId": "m1", "publishTime": "2024-01-01T00:00:00Z"},
            "subscription": "projects/x/subscriptions/y",
        }
        resp = client.post("/api/webhooks/gmail/push", json=payload)
        assert resp.json()["status"] == "ignored"
        assert resp.json()["reason"] == "missing_data"

    def test_missing_history_id_ignored(self, client):
        data = base64.b64encode(json.dumps({"emailAddress": "a@b.com"}).encode()).decode()
        payload = {
            "message": {"data": data, "messageId": "m2", "publishTime": "2024-01-01T00:00:00Z"},
            "subscription": "projects/x/subscriptions/y",
        }
        resp = client.post("/api/webhooks/gmail/push", json=payload)
        assert resp.json()["status"] == "ignored"

    def test_invalid_base64_returns_error(self, client):
        payload = {
            "message": {"data": "not-valid-base64!!!", "messageId": "m3", "publishTime": "2024-01-01T00:00:00Z"},
            "subscription": "projects/x/subscriptions/y",
        }
        resp = client.post("/api/webhooks/gmail/push", json=payload)
        assert resp.json()["status"] == "error"

    def test_invalid_json_inside_base64_returns_error(self, client):
        data = base64.b64encode(b"this is not json").decode()
        payload = {
            "message": {"data": data, "messageId": "m4", "publishTime": "2024-01-01T00:00:00Z"},
            "subscription": "projects/x/subscriptions/y",
        }
        resp = client.post("/api/webhooks/gmail/push", json=payload)
        assert resp.json()["status"] == "error"

    def test_history_id_as_integer_accepted(self, client):
        """Google sometimes sends historyId as an int — must still work."""
        data = base64.b64encode(
            json.dumps({"emailAddress": "user@gmail.com", "historyId": 99999}).encode()
        ).decode()
        payload = {
            "message": {"data": data, "messageId": "m5", "publishTime": "2024-01-01T00:00:00Z"},
            "subscription": "projects/x/subscriptions/y",
        }
        with patch("jobradar.services.sentinel.process_push_notification"):
            resp = client.post("/api/webhooks/gmail/push", json=payload)
        assert resp.json()["status"] == "accepted"


# ─────────────────────────────────────────────────────────────────────────────
# Sentinel unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSentinelProcessPushNotification:
    """Unit tests for sentinel.process_push_notification"""

    def _run(self, email: str, history_id: str):
        from jobradar.services.sentinel import process_push_notification
        process_push_notification(email, history_id)

    # ── user lookup ──────────────────────────────────────────────────────────

    def test_unknown_email_exits_silently(self, db_session):
        """No user found → should return without raising."""
        with patch("app.db.session.SessionLocal", return_value=db_session):
            self._run("nobody@nowhere.com", "100")
        # no exception raised — pass

    def test_user_without_google_token_exits_silently(self, db_session, test_user):
        test_user.google_access_token = None
        db_session.commit()

        with patch("app.db.session.SessionLocal", return_value=db_session):
            self._run(test_user.email, "100")
        # no exception raised

    # ── first-time setup (no last_history_id) ───────────────────────────────

    def test_no_last_history_id_stores_current_and_returns(self, db_session, test_user):
        test_user.google_access_token = "tok"
        test_user.last_history_id = None
        db_session.commit()

        # Pass db_session to sentinel but prevent it from closing our session.
        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch.object(db_session, "close"):
            self._run(test_user.email, "500")

        db_session.expire_all()
        user = db_session.query(User).filter_by(id=test_user.id).first()
        assert user.last_history_id == "500"
        assert db_session.query(Application).count() == 0

    # ── credential failure ───────────────────────────────────────────────────

    def test_credential_error_exits_without_updating_history_id(self, db_session, test_user):
        """When credentials fail to load sentinel returns early — history_id stays unchanged."""
        test_user.google_access_token = "bad-token"
        test_user.last_history_id = "400"
        db_session.commit()

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch.object(db_session, "close"), \
             patch("app.services.google_oauth.get_credentials_for_user", side_effect=Exception("bad creds")):
            self._run(test_user.email, "500")

        db_session.expire_all()
        user = db_session.query(User).filter_by(id=test_user.id).first()
        # Sentinel returns early on credential failure — last_history_id unchanged
        assert user.last_history_id == "400"

    # ── incremental fetch failure ────────────────────────────────────────────

    def test_incremental_fetch_failure_updates_history_id(self, db_session, test_user):
        test_user.google_access_token = "tok"
        test_user.last_history_id = "400"
        db_session.commit()

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch.object(db_session, "close"), \
             patch("app.services.google_oauth.get_credentials_for_user", return_value=MagicMock()), \
             patch("jobradar.services.gmail_service.get_incremental_messages", side_effect=Exception("Gmail error")):
            self._run(test_user.email, "500")

        db_session.expire_all()
        user = db_session.query(User).filter_by(id=test_user.id).first()
        assert user.last_history_id == "500"

    # ── no new messages ──────────────────────────────────────────────────────

    def test_no_new_messages_updates_history_id(self, db_session, test_user):
        test_user.google_access_token = "tok"
        test_user.last_history_id = "400"
        db_session.commit()

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch.object(db_session, "close"), \
             patch("app.services.google_oauth.get_credentials_for_user", return_value=MagicMock()), \
             patch("jobradar.services.gmail_service.get_incremental_messages", return_value=[]):
            self._run(test_user.email, "500")

        db_session.expire_all()
        user = db_session.query(User).filter_by(id=test_user.id).first()
        assert user.last_history_id == "500"
        assert db_session.query(Application).count() == 0

    # ── non-job thread skipped ───────────────────────────────────────────────

    def test_non_job_thread_not_classified(self, db_session, test_user):
        test_user.google_access_token = "tok"
        test_user.last_history_id = "400"
        db_session.commit()

        msg_meta = {
            "id": "msg-1",
            "threadId": "thread-1",
            "snippet": "Your Amazon order has shipped",
            "payload": {"headers": [{"name": "Subject", "value": "Order shipped"}]},
        }

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch("app.services.google_oauth.get_credentials_for_user", return_value=MagicMock()), \
             patch("jobradar.services.gmail_service.get_incremental_messages", return_value=["msg-1"]), \
             patch("jobradar.services.gmail_service.get_thread_by_message", return_value=msg_meta), \
             patch("jobradar.services.classifier.classify_thread") as mock_classify:
            self._run(test_user.email, "500")

        mock_classify.assert_not_called()
        assert db_session.query(Application).count() == 0

    # ── LLM returns None (not job-related) ──────────────────────────────────

    def test_llm_not_job_related_no_application_created(self, db_session, test_user):
        test_user.google_access_token = "tok"
        test_user.last_history_id = "400"
        db_session.commit()

        msg_meta = {
            "id": "msg-1",
            "threadId": "thread-1",
            "snippet": "congratulations on your interview scheduled",
            "payload": {"headers": [{"name": "Subject", "value": "Interview scheduled"}]},
        }

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch("app.services.google_oauth.get_credentials_for_user", return_value=MagicMock()), \
             patch("jobradar.services.gmail_service.get_incremental_messages", return_value=["msg-1"]), \
             patch("jobradar.services.gmail_service.get_thread_by_message", return_value=msg_meta), \
             patch("jobradar.services.gmail_service.get_thread_messages", return_value=_fake_messages()), \
             patch("jobradar.services.classifier.classify_thread", return_value=None):
            self._run(test_user.email, "500")

        assert db_session.query(Application).count() == 0

    # ── new application created ──────────────────────────────────────────────

    def test_new_job_thread_creates_application_and_history(self, db_session, test_user):
        test_user.google_access_token = "tok"
        test_user.last_history_id = "400"
        db_session.commit()

        msg_meta = {
            "id": "msg-1",
            "threadId": "thread-new",
            "snippet": "thank you for applying to the software engineer role",
            "payload": {"headers": [{"name": "Subject", "value": "Application received"}]},
        }

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch.object(db_session, "close"), \
             patch("app.services.google_oauth.get_credentials_for_user", return_value=MagicMock()), \
             patch("jobradar.services.gmail_service.get_incremental_messages", return_value=["msg-1"]), \
             patch("jobradar.services.gmail_service.get_thread_by_message", return_value=msg_meta), \
             patch("jobradar.services.gmail_service.get_thread_messages", return_value=_fake_messages()), \
             patch("jobradar.services.classifier.classify_thread", return_value=_classifier_output()), \
             patch("time.sleep"):
            self._run(test_user.email, "500")

        db_session.expire_all()
        apps = db_session.query(Application).all()
        assert len(apps) == 1
        saved = apps[0]
        assert saved.company == "Acme Corp"
        assert saved.role == "Software Engineer"
        assert saved.current_status == "applied"
        assert saved.email_thread_id == "thread-new"
        assert saved.user_id == test_user.id
        assert saved.confidence == 0.92
        assert saved.low_confidence is False

        history = db_session.query(StatusHistory).filter_by(application_id=saved.id).all()
        assert len(history) == 1
        assert history[0].status == "applied"
        assert history[0].summary == "Applied for SWE role"

    # ── existing application — no status change ──────────────────────────────

    def test_existing_application_same_status_not_updated(self, db_session, test_user):
        test_user.google_access_token = "tok"
        test_user.last_history_id = "400"
        db_session.commit()

        existing = Application(
            user_id=test_user.id,
            company="Acme Corp",
            role="Software Engineer",
            current_status="applied",
            email_thread_id="thread-existing",
            last_activity=datetime.utcnow(),
            confidence=0.9,
            low_confidence=False,
        )
        db_session.add(existing)
        db_session.commit()

        msg_meta = {
            "id": "msg-2",
            "threadId": "thread-existing",
            "snippet": "application received",
            "payload": {"headers": [{"name": "Subject", "value": "Application received"}]},
        }

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch.object(db_session, "close"), \
             patch("app.services.google_oauth.get_credentials_for_user", return_value=MagicMock()), \
             patch("jobradar.services.gmail_service.get_incremental_messages", return_value=["msg-2"]), \
             patch("jobradar.services.gmail_service.get_thread_by_message", return_value=msg_meta), \
             patch("jobradar.services.gmail_service.get_thread_messages", return_value=_fake_messages()), \
             patch("jobradar.services.classifier.classify_thread", return_value=_classifier_output(status="applied")), \
             patch("time.sleep"):
            self._run(test_user.email, "500")

        # Still only 1 application, no new history
        db_session.expire_all()
        assert db_session.query(Application).count() == 1
        assert db_session.query(StatusHistory).count() == 0

    # ── existing application — status changed ────────────────────────────────

    def test_existing_application_status_change_updates_and_adds_history(self, db_session, test_user):
        test_user.google_access_token = "tok"
        test_user.last_history_id = "400"
        db_session.commit()

        existing = Application(
            user_id=test_user.id,
            company="Acme Corp",
            role="Software Engineer",
            current_status="applied",
            email_thread_id="thread-existing",
            last_activity=datetime.utcnow(),
            confidence=0.9,
            low_confidence=False,
        )
        db_session.add(existing)
        db_session.commit()
        db_session.refresh(existing)
        app_id = existing.id

        msg_meta = {
            "id": "msg-3",
            "threadId": "thread-existing",
            "snippet": "interview scheduled for next week",
            "payload": {"headers": [{"name": "Subject", "value": "Interview scheduled"}]},
        }

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch.object(db_session, "close"), \
             patch("app.services.google_oauth.get_credentials_for_user", return_value=MagicMock()), \
             patch("jobradar.services.gmail_service.get_incremental_messages", return_value=["msg-3"]), \
             patch("jobradar.services.gmail_service.get_thread_by_message", return_value=msg_meta), \
             patch("jobradar.services.gmail_service.get_thread_messages", return_value=_fake_messages()), \
             patch("jobradar.services.classifier.classify_thread",
                   return_value=_classifier_output(status="interview_scheduled", summary="Got an interview!")), \
             patch("time.sleep"):
            self._run(test_user.email, "500")

        db_session.expire_all()
        saved = db_session.query(Application).filter_by(id=app_id).first()
        assert saved.current_status == "interview_scheduled"

        history = db_session.query(StatusHistory).filter_by(application_id=app_id).all()
        assert len(history) == 1
        assert history[0].status == "interview_scheduled"
        assert history[0].summary == "Got an interview!"

    # ── duplicate thread in same push batch ──────────────────────────────────

    def test_duplicate_thread_ids_in_batch_processed_only_once(self, db_session, test_user):
        """If two message IDs map to the same thread, only one application is created."""
        test_user.google_access_token = "tok"
        test_user.last_history_id = "400"
        db_session.commit()

        msg_meta = {
            "id": "msg-x",
            "threadId": "thread-dup",
            "snippet": "application received",
            "payload": {"headers": [{"name": "Subject", "value": "Application received"}]},
        }

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch("app.services.google_oauth.get_credentials_for_user", return_value=MagicMock()), \
             patch("jobradar.services.gmail_service.get_incremental_messages", return_value=["msg-x1", "msg-x2"]), \
             patch("jobradar.services.gmail_service.get_thread_by_message", return_value=msg_meta), \
             patch("jobradar.services.gmail_service.get_thread_messages", return_value=_fake_messages()), \
             patch("jobradar.services.classifier.classify_thread", return_value=_classifier_output()), \
             patch("time.sleep"):
            self._run(test_user.email, "500")

        assert db_session.query(Application).count() == 1

    # ── low confidence flag ──────────────────────────────────────────────────

    def test_low_confidence_application_flagged(self, db_session, test_user):
        test_user.google_access_token = "tok"
        test_user.last_history_id = "400"
        db_session.commit()

        msg_meta = {
            "id": "msg-lc",
            "threadId": "thread-low",
            "snippet": "recruiter reached out",
            "payload": {"headers": [{"name": "Subject", "value": "Opportunity"}]},
        }

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch("app.services.google_oauth.get_credentials_for_user", return_value=MagicMock()), \
             patch("jobradar.services.gmail_service.get_incremental_messages", return_value=["msg-lc"]), \
             patch("jobradar.services.gmail_service.get_thread_by_message", return_value=msg_meta), \
             patch("jobradar.services.gmail_service.get_thread_messages", return_value=_fake_messages()), \
             patch("jobradar.services.classifier.classify_thread",
                   return_value=_classifier_output(confidence=0.50)), \
             patch("time.sleep"):
            self._run(test_user.email, "500")

        app = db_session.query(Application).first()
        assert app is not None
        assert app.low_confidence is True
        assert app.confidence == 0.50

    # ── history_id updated after processing ──────────────────────────────────

    def test_history_id_updated_after_processing(self, db_session, test_user):
        test_user.google_access_token = "tok"
        test_user.last_history_id = "400"
        db_session.commit()

        with patch("app.db.session.SessionLocal", return_value=db_session), \
             patch.object(db_session, "close"), \
             patch("app.services.google_oauth.get_credentials_for_user", return_value=MagicMock()), \
             patch("jobradar.services.gmail_service.get_incremental_messages", return_value=[]):
            self._run(test_user.email, "9999")

        db_session.expire_all()
        user = db_session.query(User).filter_by(id=test_user.id).first()
        assert user.last_history_id == "9999"


# ─────────────────────────────────────────────────────────────────────────────
# Payload decoding helpers (pure unit tests — no DB needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestPubSubPayloadDecoding:
    """Verify the base64 + JSON decode logic used inside the webhook handler."""

    def test_standard_payload_decodes(self):
        payload = _make_pubsub_payload("alice@gmail.com", "77777")
        raw = base64.b64decode(payload["message"]["data"]).decode()
        data = json.loads(raw)
        assert data["emailAddress"] == "alice@gmail.com"
        assert str(data["historyId"]) == "77777"

    def test_history_id_as_int_survives_roundtrip(self):
        data = base64.b64encode(
            json.dumps({"emailAddress": "x@y.com", "historyId": 12345}).encode()
        ).decode()
        decoded = json.loads(base64.b64decode(data).decode())
        assert decoded["historyId"] == 12345
