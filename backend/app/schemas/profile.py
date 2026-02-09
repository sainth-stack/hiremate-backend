"""
Profile Pydantic schemas - matches PROFILE_PAYLOAD_SCHEMA format
"""
from typing import List, Optional

from pydantic import BaseModel, Field


# --- Nested schemas ---
class Experience(BaseModel):
    jobTitle: str = ""
    companyName: str = ""
    employmentType: str = ""
    startDate: str = ""
    endDate: str = ""
    location: str = ""
    workMode: str = ""
    description: str = ""
    techStack: str = ""


class Education(BaseModel):
    degree: str = ""
    fieldOfStudy: str = ""
    institution: str = ""
    startYear: str = ""
    endYear: str = ""
    grade: str = ""
    location: str = ""


class TechSkill(BaseModel):
    name: str = ""
    level: str = ""
    years: str = ""


class SoftSkill(BaseModel):
    name: str = ""


class Project(BaseModel):
    name: str = ""
    description: str = ""
    role: str = ""
    techStack: str = ""
    githubUrl: str = ""
    liveUrl: str = ""
    projectType: str = ""


class Preferences(BaseModel):
    desiredRoles: str = ""
    employmentType: List[str] = Field(default_factory=list)
    experienceLevel: str = ""
    openToRemote: str = ""
    willingToRelocate: str = ""
    preferredLocations: List[str] = Field(default_factory=list)
    expectedSalaryRange: str = ""


class OtherLink(BaseModel):
    label: str = ""
    url: str = ""


class Links(BaseModel):
    linkedInUrl: str = ""
    githubUrl: str = ""
    portfolioUrl: str = ""
    otherLinks: List[OtherLink] = Field(default_factory=list)


class ProfilePayload(BaseModel):
    """Full profile schema - matches frontend PROFILE_PAYLOAD_SCHEMA"""
    resumeUrl: Optional[str] = None
    resumeLastUpdated: Optional[str] = None
    firstName: str = ""
    lastName: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    country: str = ""
    willingToWorkIn: List[str] = Field(default_factory=list)
    professionalHeadline: str = ""
    professionalSummary: str = ""
    experiences: List[Experience] = Field(default_factory=list)
    educations: List[Education] = Field(default_factory=list)
    techSkills: List[TechSkill] = Field(default_factory=list)
    softSkills: List[SoftSkill] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    preferences: Preferences = Field(default_factory=Preferences)
    links: Links = Field(default_factory=Links)

    model_config = {"extra": "ignore"}


def profile_model_to_payload(profile) -> ProfilePayload:
    """Convert Profile DB model to ProfilePayload schema"""
    prefs = profile.preferences if isinstance(profile.preferences, dict) else {}
    lnks = profile.links if isinstance(profile.links, dict) else {}
    raw_other = lnks.get("otherLinks", lnks.get("other_links", [])) or []
    other_links = [
        {"label": (o.get("label", "") if isinstance(o, dict) else getattr(o, "label", "")),
         "url": (o.get("url", "") if isinstance(o, dict) else getattr(o, "url", ""))}
        for o in raw_other
    ]
    return ProfilePayload(
        resumeUrl=profile.resume_url,
        resumeLastUpdated=profile.resume_last_updated,
        firstName=profile.first_name or "",
        lastName=profile.last_name or "",
        email=profile.email or "",
        phone=profile.phone or "",
        city=profile.city or "",
        country=profile.country or "",
        willingToWorkIn=profile.willing_to_work_in or [],
        professionalHeadline=profile.professional_headline or "",
        professionalSummary=profile.professional_summary or "",
        experiences=[Experience.model_validate(e) for e in (profile.experiences or [])],
        educations=[Education.model_validate(e) for e in (profile.educations or [])],
        techSkills=[TechSkill.model_validate(s) for s in (profile.tech_skills or [])],
        softSkills=[SoftSkill.model_validate(s) for s in (profile.soft_skills or [])],
        projects=[Project.model_validate(p) for p in (profile.projects or [])],
        preferences=Preferences(**{**Preferences().model_dump(), **prefs}),
        links=Links(**{k: v for k, v in {**Links().model_dump(), **lnks}.items() if k != "otherLinks"}, otherLinks=other_links),
    )


def payload_to_profile_dict(payload: ProfilePayload) -> dict:
    """Convert ProfilePayload to DB model kwargs"""
    return {
        "resume_url": payload.resumeUrl,
        "resume_last_updated": payload.resumeLastUpdated,
        "first_name": payload.firstName,
        "last_name": payload.lastName,
        "email": payload.email,
        "phone": payload.phone,
        "city": payload.city,
        "country": payload.country,
        "willing_to_work_in": payload.willingToWorkIn,
        "professional_headline": payload.professionalHeadline,
        "professional_summary": payload.professionalSummary,
        "experiences": [e.model_dump() for e in payload.experiences],
        "educations": [e.model_dump() for e in payload.educations],
        "tech_skills": [s.model_dump() for s in payload.techSkills],
        "soft_skills": [s.model_dump() for s in payload.softSkills],
        "projects": [p.model_dump() for p in payload.projects],
        "preferences": payload.preferences.model_dump(),
        "links": payload.links.model_dump(),
    }
