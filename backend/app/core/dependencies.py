"""
Dependency injection utilities
"""
from datetime import datetime
from fastapi import Depends, HTTPException, Query, status, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.token_pricing import TokenPricing
from backend.app.db.session import SessionLocal, get_db
from backend.app.models.user import User

security = HTTPBearer(auto_error=False)


def verify_token(token: str, db: Session) -> User | None:
    """Decode JWT and return User if valid. Used for sendBeacon (no custom headers)."""
    if not token or not token.strip():
        return None
    try:
        payload = jwt.decode(
            token.strip(), settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user
    except (JWTError, ValueError):
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    token: str | None = Query(default=None, alias="token"),
    db: Session = Depends(get_db),
) -> User | None:
    """Get user from Bearer header or from token query param (for sendBeacon)."""
    if credentials and credentials.credentials:
        user = verify_token(credentials.credentials, db)
        if user:
            return user
    if token:
        return verify_token(token, db)
    return None


def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require authenticated user with is_admin=True. Raise 403 if not admin."""
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def _enforce_subscription_expiry(current_user: User, db: Session) -> None:
    """
    If the user's paid subscription has expired, downgrade them to the free plan
    and reset their token balance to the free-plan quota.
    Mutates current_user and commits to DB if a downgrade occurs.
    """
    if (
        current_user.subscription_plan != "free"
        and current_user.subscription_expiry is not None
        and current_user.subscription_expiry < datetime.utcnow()
    ):
        from backend.app.models.subscription_plan import SubscriptionPlan
        free_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == "free").first()
        current_user.subscription_plan = "free"
        if free_plan:
            current_user.token_balance = free_plan.monthly_tokens
        current_user.subscription_expiry = None
        db.add(current_user)
        db.commit()


def _is_unlimited(current_user: User, db: Session) -> bool:
    """Returns True if the user is on an unlimited (Elite) plan."""
    from backend.app.models.subscription_plan import SubscriptionPlan
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == current_user.subscription_plan
    ).first()
    return bool(plan and plan.monthly_tokens == TokenPricing.UNLIMITED_PLAN_THRESHOLD)


def check_token_balance(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """
    Router-level token enforcement applied to all protected routers.

    Rules:
    1. GET requests pass through — pure data reads (list applications, get profile,
       sync status, etc.) must never be blocked by token balance.
       NOTE: GET endpoints that trigger AI calls must add `require_ai_token_balance`
       as an explicit route-level dependency to enforce balance for those specific routes.
    2. Enforce subscription expiry: downgrade expired paid plans to free.
    3. Elite plan (monthly_tokens == -1) bypasses the balance check.
    4. Block with HTTP 403 if token_balance <= 0.
    5. Write X-Token-Balance and X-Token-Low-Balance response headers so the
       frontend can warn the user when their balance is running low.
    """
    # 1. Pure data GETs always pass — no token cost
    if request.method == "GET":
        return current_user

    # 2. Enforce subscription expiry
    _enforce_subscription_expiry(current_user, db)

    # 3. Elite (unlimited) bypass
    if _is_unlimited(current_user, db):
        response.headers["X-Token-Balance"] = "unlimited"
        response.headers["X-Token-Low-Balance"] = "false"
        return current_user

    # 4. Block if balance exhausted
    if current_user.token_balance <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your AI token balance is empty. Please upgrade your plan or wait for your monthly replenishment to continue.",
        )

    # 5. Write balance headers so frontend can show low-balance warnings
    response.headers["X-Token-Balance"] = str(current_user.token_balance)
    response.headers["X-Token-Low-Balance"] = (
        "true" if current_user.token_balance < TokenPricing.LOW_BALANCE_THRESHOLD else "false"
    )

    return current_user


def require_ai_token_balance(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """
    Explicit AI token enforcement for GET endpoints that run LLM calls.
    Use this as a route-level dependency on specific AI GET routes:
      - GET /briefing
      - GET /mock-interview/questions
      - GET /applications/{id}/salary-estimate
      - GET /applications/companies/{domain}/profile

    Applies the same expiry + Elite bypass + balance check as check_token_balance
    but without the GET method exemption.
    """
    # Enforce subscription expiry
    _enforce_subscription_expiry(current_user, db)

    # Elite (unlimited) bypass
    if _is_unlimited(current_user, db):
        response.headers["X-Token-Balance"] = "unlimited"
        response.headers["X-Token-Low-Balance"] = "false"
        return current_user

    # Block if balance exhausted
    if current_user.token_balance <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your AI token balance is empty. Please upgrade your plan or wait for your monthly replenishment to continue.",
        )

    response.headers["X-Token-Balance"] = str(current_user.token_balance)
    response.headers["X-Token-Low-Balance"] = (
        "true" if current_user.token_balance < TokenPricing.LOW_BALANCE_THRESHOLD else "false"
    )

    return current_user
