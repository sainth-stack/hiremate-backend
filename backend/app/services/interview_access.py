"""Signed tokens for passwordless interview link access."""
from __future__ import annotations

from datetime import timedelta

from jose import JWTError, jwt

from backend.app.core.config import settings
from backend.app.core.security import create_access_token

INTERVIEW_ACCESS_TYPE = "interview_access"
INTERVIEW_ACCESS_DAYS = 90


def create_interview_access_token(*, user_id: int, interview_id: int, assignment_id: int) -> str:
    return create_access_token(
        data={
            "type": INTERVIEW_ACCESS_TYPE,
            "sub": str(user_id),
            "interview_id": interview_id,
            "assignment_id": assignment_id,
        },
        expires_delta=timedelta(days=INTERVIEW_ACCESS_DAYS),
    )


def verify_interview_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired interview link") from exc

    if payload.get("type") != INTERVIEW_ACCESS_TYPE:
        raise ValueError("Invalid interview link token")
    if not payload.get("sub") or payload.get("interview_id") is None or payload.get("assignment_id") is None:
        raise ValueError("Invalid interview link token")

    return payload
