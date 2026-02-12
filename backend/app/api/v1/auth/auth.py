"""
Authentication endpoints - Login, Register, and Get Current User
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.schemas.user import UserRegister, UserLogin, TokenResponse, UserResponse
from backend.app.services.auth_service import AuthService

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
    )
