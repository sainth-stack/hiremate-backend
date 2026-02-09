"""
Profile service - create/update profile and resume data
"""
from sqlalchemy.orm import Session

from backend.app.models.profile import Profile
from backend.app.models.user import User
from backend.app.schemas.profile import ProfilePayload, payload_to_profile_dict


class ProfileService:
    @staticmethod
    def get_or_create_profile(db: Session, user: User) -> Profile:
        """Get existing profile or create empty one for user"""
        profile = db.query(Profile).filter(Profile.user_id == user.id).first()
        if not profile:
            profile = Profile(user_id=user.id)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        return profile

    @staticmethod
    def update_resume(db: Session, user: User, resume_url: str, resume_last_updated: str) -> Profile:
        """Update or create profile with resume URL and timestamp"""
        profile = ProfileService.get_or_create_profile(db, user)
        profile.resume_url = resume_url
        profile.resume_last_updated = resume_last_updated
        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    def update_profile(db: Session, user: User, payload: ProfilePayload) -> Profile:
        """Update profile with full payload (PROFILE_PAYLOAD_SCHEMA format)."""
        profile = ProfileService.get_or_create_profile(db, user)
        data = payload_to_profile_dict(payload)
        for key, value in data.items():
            setattr(profile, key, value)
        db.commit()
        db.refresh(profile)
        return profile
