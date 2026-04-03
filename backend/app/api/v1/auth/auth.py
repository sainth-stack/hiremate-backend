"""
Authentication endpoints - Login, Register, Get Current User, and Token Refresh
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user, get_db, security
from backend.app.core.logging_config import get_logger
from backend.app.core.security import create_access_token
from backend.app.models.user import User
from backend.app.schemas.user import UserRegister, UserLogin, TokenResponse, UserResponse
from backend.app.services.auth_service import AuthService
from backend.app.services import google_oauth
from fastapi.security import HTTPAuthorizationCredentials

logger = get_logger("api.auth")
router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account. Returns success and access token (user is logged in after register).

    - **first_name**: User's first name
    - **last_name**: User's last name
    - **email**: User's email address (must be unique)
    - **password**: User's password
    """
    logger.info("Registration attempt for email=%s", user_data.email)
    try:
        result = AuthService.register_user(db, user_data)

        if not result["success"]:
            logger.warning(
                "Registration failed email=%s reason=%s",
                user_data.email,
                result["message"],
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"],
            )

        user = result["user"]
        logger.info(
            "User registered successfully user_id=%s email=%s",
            user.id,
            user.email,
        )
        return TokenResponse(
            access_token=result["access_token"],
            token_type=result["token_type"],
            user=UserResponse(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                is_admin=getattr(user, "is_admin", False),
            ),
            message=result["message"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Registration error email=%s error=%s",
            user_data.email,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration error: {str(e)}",
        )


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    Login user and get access token

    - **email**: User's email address
    - **password**: User's password
    """
    logger.info("Login attempt for email=%s", login_data.email)
    try:
        result = AuthService.login_user(db, login_data)

        if not result["success"]:
            logger.warning(
                "Login failed email=%s reason=%s",
                login_data.email,
                result["message"],
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result["message"],
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = result["user"]
        logger.info(
            "User logged in successfully user_id=%s email=%s",
            user.id,
            user.email,
        )
        return TokenResponse(
            access_token=result["access_token"],
            token_type=result["token_type"],
            user=UserResponse(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                is_admin=getattr(user, "is_admin", False),
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Login error email=%s error=%s",
            login_data.email,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login error: {str(e)}",
        )


@router.get("/profile", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Get the current authenticated user's profile (id, first_name, last_name, email).
    Used to refresh auth state on app load.
    """
    return UserResponse(
        id=current_user.id,
        first_name=current_user.first_name or "",
        last_name=current_user.last_name or "",
        email=current_user.email or "",
        is_admin=getattr(current_user, "is_admin", False),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Refresh access token. Accepts current token (even if expired) and returns a new token.
    Use when token is about to expire or expired recently.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_exp": False},
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email},
            expires_delta=access_token_expires,
        )
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                id=user.id,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                email=user.email or "",
                is_admin=getattr(user, "is_admin", False),
            ),
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/google/url")
def get_google_auth_url():
    """
    Get the Google OAuth authorization URL.
    """
    try:
        url, state, code_verifier = google_oauth.get_auth_url()
        _states[state] = code_verifier  # Must store so callback can retrieve it
        return {"url": url, "state": state}
    except Exception as e:
        logger.error("Failed to generate Google auth URL: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Google auth URL: {str(e)}"
        )


# In-memory state store: maps state -> code_verifier (good enough for single-server dev)
_states: dict[str, str] = {}


@router.get("/google")
def google_login():
    """
    Redirect user to Google OAuth consent page.
    """
    try:
        auth_url, state, code_verifier = google_oauth.get_auth_url()
        _states[state] = code_verifier
        return RedirectResponse(auth_url)
    except Exception as e:
        logger.exception("Failed to generate Google auth URL: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not initialize Google login"
        )


@router.get("/google/callback")
def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    Handle Google OAuth callback (GET redirect from Google).
    Exchanges code for tokens, upserts user, and redirects to frontend with JWT.
    """
    if not code:
        raise HTTPException(status_code=400, detail="Code is required")

    # Retrieve and remove the code_verifier for this state (CSRF check + PKCE)
    code_verifier = _states.pop(state, None)
    if code_verifier is None:
        logger.warning("OAuth state mismatch or expired for state=%s", state)

    try:
        # 1. Exchange code for Google data (pass code_verifier for PKCE)
        google_user_data = google_oauth.exchange_code(code, code_verifier=code_verifier)

        # 2. Login/Register user via AuthService
        result = AuthService.login_with_google(db, google_user_data)

        if not result["success"]:
            raise HTTPException(status_code=401, detail=result["message"])

        # 3. Subscribe to Gmail watch + capture initial historyId (non-blocking)
        user = result["user"]
        try:
            from backend.jobradar.services.gmail_service import subscribe_to_watch, get_latest_history_id
            creds = google_oauth.get_credentials_for_user(db, user)

            watch_result = subscribe_to_watch(creds)
            if watch_result:
                logger.info("Gmail watch subscribed for %s (expiry: %s)", user.email, watch_result.get("expiration"))

            if not user.last_history_id:
                history_id = get_latest_history_id(creds)
                if history_id:
                    user.last_history_id = str(history_id)
                    db.commit()
                    logger.info("Initial last_history_id=%s set for %s", history_id, user.email)
        except Exception as watch_err:
            logger.warning("Gmail watch setup failed for %s (non-fatal): %s", user.email, watch_err)

        # 4. Redirect to frontend with JWT token
        access_token = result["access_token"]
        frontend_url = f"https://opsbrainai.com/auth/google/callback?token={access_token}"
        return RedirectResponse(frontend_url)

    except Exception as e:
        logger.exception("Google OAuth callback error: %s", str(e))
        return RedirectResponse(f"https://opsbrainai.com/login?error={str(e)}")



