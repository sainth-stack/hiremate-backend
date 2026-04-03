"""
Authentication service business logic
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.app.models.user import User
from backend.app.schemas.user import UserRegister, UserLogin
from backend.app.core.security import verify_password, get_password_hash, create_access_token
from backend.app.core.config import settings
from datetime import timedelta


class AuthService:
    """Service for authentication operations"""
    
    @staticmethod
    def register_user(db: Session, user_data: UserRegister):
        """Register a new user"""
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == user_data.email).first()
            if existing_user:
                return {"success": False, "message": "Email already registered"}
            
            # Hash password
            hashed_password = get_password_hash(user_data.password)
            
            # Create new user
            new_user = User(
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                email=user_data.email,
                hashed_password=hashed_password
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            # Auto-promote admin if ADMIN_EMAIL matches
            if settings.admin_email and new_user.email and new_user.email.strip().lower() == settings.admin_email.strip().lower():
                new_user.is_admin = True
                db.commit()
                db.refresh(new_user)

            # Create access token (same as login - user is logged in after register)
            access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
            access_token = create_access_token(
                data={"sub": str(new_user.id), "email": new_user.email},
                expires_delta=access_token_expires
            )
            
            return {
                "success": True,
                "user": new_user,
                "message": "User registered successfully",
                "access_token": access_token,
                "token_type": "bearer"
            }
        except IntegrityError:
            db.rollback()
            return {"success": False, "message": "Error registering user"}
    
    @staticmethod
    def login_user(db: Session, login_data: UserLogin):
        """Authenticate user and return access token"""
        # Find user by email
        user = db.query(User).filter(User.email == login_data.email).first()
        
        if not user:
            return {"success": False, "message": "Invalid email or password"}
        
        # Verify password
        if not verify_password(login_data.password, user.hashed_password):
            return {"success": False, "message": "Invalid email or password"}
        
        if not user.is_active:
            return {"success": False, "message": "User account is inactive"}

        # Auto-promote admin if ADMIN_EMAIL matches
        if settings.admin_email and user.email and user.email.strip().lower() == settings.admin_email.strip().lower():
            if not getattr(user, "is_admin", False):
                user.is_admin = True
                db.commit()
                db.refresh(user)

        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email},
            expires_delta=access_token_expires
        )
        
        return {
            "success": True,
            "access_token": access_token,
            "token_type": "bearer",
            "user": user,
            "message": "Login successful"
        }

    @staticmethod
    def login_with_google(db: Session, google_data: dict):
        """Sync user from Google data and return tokens"""
        # Try finding by google_id first
        user = db.query(User).filter(User.google_id == google_data["google_id"]).first()
        
        # fallback to email if google_id not linked yet
        if not user:
            user = db.query(User).filter(User.email == google_data["email"]).first()
            if user:
                user.google_id = google_data["google_id"]
        
        if not user:
            user = User(
                email=google_data["email"],
                first_name=google_data["first_name"],
                last_name=google_data["last_name"],
                google_id=google_data["google_id"],
                avatar_url=google_data["avatar_url"],
                is_active=1
            )
            db.add(user)
        
        user.avatar_url = google_data["avatar_url"]
        user.google_access_token = google_data["google_access_token"]
        if google_data["google_refresh_token"]:
            user.google_refresh_token = google_data["google_refresh_token"]
        user.token_expiry = google_data["token_expiry"]
        
        db.commit()
        db.refresh(user)

        from datetime import timedelta
        # Access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        # Note: we need to make sure create_access_token is imported correctly in this scope or use the one from app.core.security
        from backend.app.core.security import create_access_token
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email},
            expires_delta=access_token_expires
        )
        
        return {
            "success": True,
            "access_token": access_token,
            "token_type": "bearer",
            "user": user,
            "message": "Google login successful"
        }
