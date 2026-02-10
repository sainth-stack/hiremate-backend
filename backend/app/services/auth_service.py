"""
Authentication service business logic
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.app.models.user import User
from backend.app.schemas.user import UserRegister, UserLogin
from backend.app.core.security import verify_password, get_password_hash, create_access_token
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
            
            # Create access token (same as login - user is logged in after register)
            access_token_expires = timedelta(minutes=30)
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
        
        # Create access token
        access_token_expires = timedelta(minutes=30)
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
