"""
Job matching service - calculates match percentages between user profile and job postings.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.logging_config import get_logger
from backend.app.models.job import Job
from backend.app.models.profile import Profile

logger = get_logger("job_matching")


def calculate_experience_match(user_profile: Profile, job: Job) -> float:
    """
    Calculate experience level match (0-100).
    Based on years of experience extracted from profile vs job requirements.
    """
    if not user_profile or not user_profile.experiences:
        return 50.0
    
    # Extract experience text from experiences JSON
    experience_text = ""
    if user_profile.experiences:
        for exp in user_profile.experiences:
            if isinstance(exp, dict):
                experience_text += f"{exp.get('jobTitle', '')} {exp.get('companyName', '')} {exp.get('description', '')} "
    
    experience_text = experience_text.lower()
    job_desc = (job.description or "").lower()
    job_title = (job.title or "").lower()
    
    user_years = _extract_years_of_experience(experience_text)
    
    required_years = _extract_required_years(job_desc, job_title)
    
    if required_years is None:
        if "senior" in job_title or "sr." in job_title or "lead" in job_title:
            required_years = 5
        elif "junior" in job_title or "jr." in job_title or "entry" in job_title:
            required_years = 1
        else:
            required_years = 3
    
    if user_years >= required_years:
        return 100.0
    elif user_years >= required_years * 0.7:
        return 85.0
    elif user_years >= required_years * 0.5:
        return 70.0
    elif user_years >= required_years * 0.3:
        return 55.0
    else:
        return 40.0


def calculate_skills_match(user_profile: Profile, job: Job) -> float:
    """
    Calculate skills match (0-100).
    Based on skill overlap between profile and job description.
    """
    if not user_profile:
        return 50.0
    
    user_skills = _extract_skills_from_profile(user_profile)
    job_skills = _extract_skills_from_job(job)
    
    if not job_skills:
        return 75.0
    
    if not user_skills:
        return 50.0
    
    user_skills_lower = {s.lower() for s in user_skills}
    job_skills_lower = {s.lower() for s in job_skills}
    
    matched = user_skills_lower.intersection(job_skills_lower)
    match_ratio = len(matched) / len(job_skills_lower) if job_skills_lower else 0
    
    if match_ratio >= 0.8:
        return 95.0
    elif match_ratio >= 0.6:
        return 85.0
    elif match_ratio >= 0.4:
        return 70.0
    elif match_ratio >= 0.2:
        return 55.0
    else:
        return 40.0


def calculate_industry_match(user_profile: Profile, job: Job) -> float:
    """
    Calculate industry experience match (0-100).
    Based on company/industry background.
    """
    if not user_profile:
        return 60.0
    
    # Extract experience text from experiences JSON
    user_exp = ""
    user_company = ""
    if user_profile.experiences and len(user_profile.experiences) > 0:
        first_exp = user_profile.experiences[0]
        if isinstance(first_exp, dict):
            user_company = (first_exp.get('companyName', '')).lower()
            user_exp = f"{first_exp.get('jobTitle', '')} {first_exp.get('description', '')}".lower()
    
    job_company = (job.company or "").lower()
    job_desc = (job.description or "").lower()
    
    industry_keywords = _extract_industry_keywords(job_desc, job_company)
    
    if not industry_keywords:
        return 70.0
    
    matched_keywords = sum(
        1 for keyword in industry_keywords
        if keyword in user_exp or keyword in user_company
    )
    
    match_ratio = matched_keywords / len(industry_keywords) if industry_keywords else 0
    
    if match_ratio >= 0.5:
        return 85.0
    elif match_ratio >= 0.3:
        return 70.0
    elif match_ratio >= 0.1:
        return 60.0
    else:
        return 50.0


def calculate_overall_match(
    experience_match: float,
    skills_match: float,
    industry_match: float,
) -> float:
    """Calculate weighted overall match score."""
    weights = {
        "experience": 0.35,
        "skills": 0.45,
        "industry": 0.20,
    }
    
    overall = (
        experience_match * weights["experience"]
        + skills_match * weights["skills"]
        + industry_match * weights["industry"]
    )
    
    return round(overall, 1)


def format_match_data_for_client(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize match payload for API consumers (camelCase + snake_case)."""
    return {
        "overall": raw.get("overall", 0),
        "experience_level": raw.get("experience_level", 0),
        "skills": raw.get("skills", 0),
        "industry_experience": raw.get("industry_experience", 0),
        "description": raw.get("description", ""),
        "experienceLevel": raw.get("experience_level", 0),
        "industryExperience": raw.get("industry_experience", 0),
    }


def calculate_job_match(user_profile: Profile, job: Job) -> dict[str, Any]:
    """
    Calculate complete match data for a job.
    
    Returns:
        {
            "overall": 85.0,
            "experience_level": 100.0,
            "skills": 80.0,
            "industry_experience": 72.0,
            "description": "Match description"
        }
    """
    experience_match = calculate_experience_match(user_profile, job)
    skills_match = calculate_skills_match(user_profile, job)
    industry_match = calculate_industry_match(user_profile, job)
    overall_match = calculate_overall_match(experience_match, skills_match, industry_match)
    
    description = _generate_match_description(job, overall_match)
    
    return format_match_data_for_client(
        {
            "overall": int(overall_match),
            "experience_level": int(experience_match),
            "skills": int(skills_match),
            "industry_experience": int(industry_match),
            "description": description,
        }
    )


def _extract_years_of_experience(experience_text: str) -> int:
    """Extract years of experience from text."""
    patterns = [
        r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience",
        r"experience:?\s*(\d+)\+?\s*(?:years?|yrs?)",
        r"(\d+)\+?\s*(?:years?|yrs?)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, experience_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    return 2


def _extract_required_years(job_desc: str, job_title: str) -> int | None:
    """Extract required years from job description."""
    combined = f"{job_title} {job_desc}"
    
    patterns = [
        r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:relevant\s+)?experience\s+required",
        r"minimum\s+(?:of\s+)?(\d+)\+?\s*(?:years?|yrs?)",
        r"(\d+)\+?\s*(?:years?|yrs?)\s+experience",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    return None


def _extract_skills_from_profile(user_profile: Profile) -> set[str]:
    """Extract skills from user profile."""
    skills = set()
    
    # Extract from tech_skills
    if user_profile.tech_skills:
        for skill in user_profile.tech_skills:
            if isinstance(skill, dict):
                skills.add(skill.get('name', ''))
            elif isinstance(skill, str):
                skills.add(skill)
    
    # Extract from skill_categories
    if user_profile.skill_categories:
        for category in user_profile.skill_categories:
            if isinstance(category, dict):
                for skill in category.get('skills', []):
                    if isinstance(skill, dict):
                        skills.add(skill.get('name', ''))
                    elif isinstance(skill, str):
                        skills.add(skill)
    
    # Extract from experiences
    if user_profile.experiences:
        common_tech = [
            "python", "java", "javascript", "typescript", "react", "node",
            "angular", "vue", "django", "flask", "fastapi", "spring",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
            "sql", "postgresql", "mysql", "mongodb", "redis", "git"
        ]
        for exp in user_profile.experiences:
            if isinstance(exp, dict):
                exp_text = f"{exp.get('jobTitle', '')} {exp.get('description', '')}".lower()
                for tech in common_tech:
                    if tech in exp_text:
                        skills.add(tech.title())
    
    return skills


def _extract_skills_from_job(job: Job) -> set[str]:
    """Extract required skills from job description."""
    skills = set()
    combined = f"{job.title} {job.description or ''}".lower()
    
    tech_keywords = [
        "python", "java", "javascript", "typescript", "react", "node",
        "angular", "vue", "django", "flask", "fastapi", "spring",
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
        "sql", "postgresql", "mysql", "mongodb", "redis", "git",
        "machine learning", "ai", "data science", "devops", "ci/cd"
    ]
    
    for tech in tech_keywords:
        if tech in combined:
            skills.add(tech.title())
    
    return skills


def _extract_industry_keywords(job_desc: str, job_company: str) -> list[str]:
    """Extract industry-specific keywords."""
    industries = {
        "fintech": ["financial", "banking", "payment", "finance", "trading"],
        "healthcare": ["health", "medical", "hospital", "patient", "clinical"],
        "ecommerce": ["ecommerce", "retail", "shopping", "marketplace"],
        "saas": ["saas", "software", "platform", "enterprise"],
        "ai": ["artificial intelligence", "machine learning", "ai", "ml", "nlp"],
        "crypto": ["blockchain", "crypto", "web3", "defi"],
    }
    
    combined = f"{job_company} {job_desc}".lower()
    keywords = []
    
    for industry, terms in industries.items():
        for term in terms:
            if term in combined:
                keywords.append(term)
    
    return keywords[:5]


def _generate_match_description(job: Job, match_score: float) -> str:
    """Generate a description for why the job matches."""
    company = job.company or "This company"
    
    if match_score >= 85:
        return f"{company} is seeking a highly motivated and skilled professional that aligns perfectly with your background and experience."
    elif match_score >= 70:
        return f"{company} is looking for talented professionals with skills and experience similar to yours."
    else:
        return f"This role at {company} may be a good fit based on your profile."
