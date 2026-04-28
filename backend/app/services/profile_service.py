"""
Profile service - create/update profile and resume data
"""
from sqlalchemy.orm import Session

from backend.app.models.profile import Profile
from backend.app.models.user import User
from backend.app.schemas.profile import ProfilePayload, payload_to_profile_dict, SkillCategory


def migrate_legacy_skills_to_categories(payload: ProfilePayload) -> None:
    """
    Migrate old techSkills/softSkills structure to new skillCategories structure.
    If skillCategories is empty but techSkills/softSkills exist, convert them.
    """
    # Only migrate if we have legacy skills but no skill categories
    if not payload.skillCategories and (payload.techSkills or payload.softSkills):
        categories = []
        
        # Migrate technical skills
        if payload.techSkills:
            tech_skills = [s.name for s in payload.techSkills if s.name.strip()]
            if tech_skills:
                categories.append(SkillCategory(
                    categoryName="Technical Skills",
                    skills=tech_skills,
                    order=0
                ))
        
        # Migrate soft skills
        if payload.softSkills:
            soft_skills = [s.name for s in payload.softSkills if s.name.strip()]
            if soft_skills:
                categories.append(SkillCategory(
                    categoryName="Soft Skills",
                    skills=soft_skills,
                    order=1
                ))
        
        payload.skillCategories = categories


def build_resume_text_from_payload(payload: ProfilePayload) -> str:
    """Build resume text string from profile payload for keyword matching."""
    parts = [
        payload.professionalSummary or "",
        f"Headline: {payload.professionalHeadline or ''}",
    ]
    for e in payload.experiences or []:
        line = f"{e.jobTitle} at {e.companyName} ({e.startDate}-{e.endDate}): {e.description}"
        pc = (getattr(e, "payrollCompany", None) or "").strip()
        if pc:
            line += f"\nPayroll company: {pc}"
        parts.append(line)
    for e in payload.educations or []:
        parts.append(f"{e.degree}, {e.institution} ({e.startYear}-{e.endYear})")
    
    # Include skills from both old and new structure
    for s in payload.techSkills or []:
        parts.append(f"Skill: {s.name} ({s.level})")
    for category in payload.skillCategories or []:
        for skill in category.skills:
            parts.append(f"Skill: {skill}")
    
    return "\n\n".join(filter(None, parts))


class ProfileService:
    @staticmethod
    def get_or_create_profile(db: Session, user: User) -> Profile:
        """Get existing profile or create one pre-seeded with the user's identity fields."""
        profile = db.query(Profile).filter(Profile.user_id == user.id).first()
        if not profile:
            profile = Profile(
                user_id=user.id,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                email=user.email or "",
            )
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
        # Migrate legacy skills structure if needed
        migrate_legacy_skills_to_categories(payload)
        
        profile = ProfileService.get_or_create_profile(db, user)
        data = payload_to_profile_dict(payload)
        for key, value in data.items():
            setattr(profile, key, value)
        db.commit()
        db.refresh(profile)
        return profile
