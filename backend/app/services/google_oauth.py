import jwt
import datetime
import secrets
import hashlib
import base64
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from cryptography.fernet import Fernet
import json

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger

logger = get_logger("services.google_oauth")

# Initialize Fernet for token encryption
try:
    fernet = Fernet(settings.encryption_key.encode())
except Exception as e:
    logger.warning("Fernet initialization failed: %s. Using a dummy key for development.", e)
    fernet = Fernet(Fernet.generate_key())

def encrypt(text: str) -> str:
    if not text:
        return None
    return fernet.encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    if not token:
        return None
    return fernet.decrypt(token.encode()).decode()

def get_oauth_flow() -> Flow:
    client_config = {
        "web": {
            "client_id":                  settings.google_client_id,
            "client_secret":              settings.google_client_secret,
            "auth_uri":                   "https://accounts.google.com/o/oauth2/auth",
            "token_uri":                  "https://oauth2.googleapis.com/token",
            "redirect_uris":              [settings.google_redirect_uri],
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=settings.google_scopes,
    )
    flow.redirect_uri = settings.google_redirect_uri
    return flow

def _generate_pkce_pair() -> tuple[str, str]:
    """Generate (code_verifier, code_challenge) for PKCE."""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode()
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()
    return code_verifier, code_challenge


def get_auth_url() -> tuple[str, str, str]:
    """Returns (auth_url, state, code_verifier) — store code_verifier indexed by state for callback."""
    flow = get_oauth_flow()
    code_verifier, code_challenge = _generate_pkce_pair()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    return auth_url, state, code_verifier


def exchange_code(code: str, code_verifier: str = None) -> dict:
    """Exchange OAuth code for tokens + user info."""
    flow = get_oauth_flow()
    flow.fetch_token(code=code, code_verifier=code_verifier)
    creds = flow.credentials

    # Fetch basic profile info
    service = build("oauth2", "v2", credentials=creds)
    user_info = service.userinfo().get().execute()

    return {
        "google_id":            user_info["id"],
        "email":                user_info["email"],
        "first_name":           user_info.get("given_name", ""),
        "last_name":            user_info.get("family_name", ""),
        "avatar_url":           user_info.get("picture"),
        "google_access_token":  encrypt(creds.token),
        "google_refresh_token": encrypt(creds.refresh_token) if creds.refresh_token else None,
        "token_expiry":         creds.expiry if creds.expiry else None,
    }

def get_credentials_for_user(db, user) -> Credentials:
    """Load + auto-refresh Google credentials for a user and persist to DB."""
    creds = Credentials(
        token=         decrypt(user.google_access_token),
        refresh_token= decrypt(user.google_refresh_token) if user.google_refresh_token else None,
        token_uri=     "https://oauth2.googleapis.com/token",
        client_id=     settings.google_client_id,
        client_secret= settings.google_client_secret,
        scopes=        settings.google_scopes,
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Persist refreshed tokens
            user.google_access_token = encrypt(creds.token)
            if creds.expiry:
                user.token_expiry = creds.expiry
            db.commit()
            db.refresh(user)
            logger.info("Successfully refreshed and persisted Google tokens for user_id=%s", user.id)
        except Exception as e:
            logger.error("Failed to refresh Google tokens for user_id=%s: %s", user.id, e)
            db.rollback()
        
    return creds
