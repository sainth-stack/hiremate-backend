"""
AI-powered salary estimation service.
Estimates salary ranges based on role, company, industry, location, and user profile.
"""
import json
import re
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from backend.jobradar.models.application import Application, CompanyProfile
from backend.app.models.user import User


SALARY_ESTIMATION_PROMPT = """You are a salary estimation expert with access to global compensation data.

**User Profile:**
- Years of Experience: {years_of_experience}
- Skills: {skills}
- Current Location: {current_location}
- Current Salary: {current_salary}

**Job Details:**
- Role: {role}
- Seniority Level: {seniority}
- Company: {company}
- Industry: {industry}
- Company Size: {company_size}
- Location: {job_location}
- Job Description Salary Range: {jd_salary_range}

**Task:**
Estimate the realistic salary range for this position considering:
1. Role seniority and responsibilities
2. Industry standards and company size
3. Location cost of living (compare to major tech hubs)
4. User's years of experience and skill alignment
5. JD salary range as anchor if provided
6. Current market conditions (2026)

Return ONLY a JSON object with:
- estimated_min: integer (annual salary minimum)
- estimated_max: integer (annual salary maximum)
- currency: "INR"|"USD"|"GBP"|"EUR" (match job location or user location)
- confidence: "low"|"medium"|"high" (based on data availability)
- rationale: string (2 sentences max explaining the estimate)
- data_sources_note: string (brief note on what data informed this estimate)

**Important:**
- Use the JD salary range as primary anchor if available
- For Indian locations (Bangalore, Mumbai, Delhi, Hyderabad, etc.), ALWAYS use INR currency
- For US/international locations, use USD/GBP/EUR as appropriate
- Indian salary ranges: Junior (3-8 LPA), Mid (8-18 LPA), Senior (18-35 LPA), Staff+ (35-80 LPA)
- US salary ranges: Junior ($60-90K), Mid ($90-140K), Senior ($140-200K), Staff+ ($200-400K)
- Consider remote vs on-site compensation differences
- Junior: 0-2 YoE, Mid: 3-5 YoE, Senior: 6-8 YoE, Staff+: 9+ YoE
- Factor in hot skills (AI/ML, Cloud, Full-stack, etc.) premium (10-30% higher)
- Be conservative with confidence if data is sparse

Return ONLY valid JSON. No explanation, no markdown, no code fences."""


def estimate_salary(db: Session, user_id: int, application_id: int) -> dict:
    """
    AI-powered salary estimation for an application.
    Returns dict with estimated_min, estimated_max, currency, confidence, rationale, data_sources_note.
    Also caches the result on the application.
    """
    from backend.jobradar.services.llm_factory import LLMFactory
    
    # Load application and related data
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        return {"error": "Application not found"}
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    
    # Load company profile if available
    company_profile = None
    if application.company_profile_id:
        company_profile = db.query(CompanyProfile).filter(CompanyProfile.id == application.company_profile_id).first()
    
    # Extract seniority from role title
    seniority = _extract_seniority(application.role)
    
    # Build prompt data
    years_of_experience = getattr(user, 'years_of_experience', None) or "Not specified"
    skills = getattr(user, 'skills', None) or []
    if isinstance(skills, list):
        skills_str = ", ".join(skills) if skills else "Not specified"
    else:
        skills_str = "Not specified"
    
    current_location = getattr(user, 'current_location', None) or "Not specified"
    current_salary = getattr(user, 'current_salary', None)
    current_salary_str = f"${current_salary:,}" if current_salary else "Not specified"
    
    industry = company_profile.industry if company_profile else "Not specified"
    company_size = company_profile.size_range if company_profile else "Not specified"
    job_location = company_profile.hq_location if company_profile else current_location
    
    # Infer currency from location (prioritize job location, fallback to user location)
    preferred_currency = _infer_currency_from_location(job_location) or _infer_currency_from_location(current_location) or "INR"
    
    # JD salary range as anchor
    jd_salary_range = "Not specified"
    if application.salary_min and application.salary_max:
        currency_symbol = _get_currency_symbol(application.salary_currency)
        jd_salary_range = f"{currency_symbol}{application.salary_min:,} - {currency_symbol}{application.salary_max:,} {application.salary_currency}"
    
    prompt = SALARY_ESTIMATION_PROMPT.format(
        years_of_experience=years_of_experience,
        skills=skills_str,
        current_location=current_location,
        current_salary=current_salary_str,
        role=application.role,
        seniority=seniority,
        company=application.company,
        industry=industry,
        company_size=company_size,
        job_location=job_location,
        jd_salary_range=jd_salary_range,
    )
    
    # Add explicit currency instruction
    prompt += f"\n\n**IMPORTANT: You MUST use {preferred_currency} as the currency for this estimate based on the location. Return estimated_min and estimated_max in {preferred_currency} only.**"
    
    # Call LLM
    try:
        provider = LLMFactory.get_provider()
        raw = provider.generate(
            system_prompt="",
            user_prompt=prompt,
            user_id=user_id,
            email=user.email,
            feature="salary_estimation"
        )
        
        # Parse JSON response
        data = json.loads(raw.strip())
        
        # Override currency if LLM returned wrong one
        if data.get("currency") != preferred_currency:
            print(f"LLM returned {data.get('currency')}, overriding to {preferred_currency}")
            data["currency"] = preferred_currency
        
        # Cache result on application
        application.salary_estimated_min = data.get("estimated_min")
        application.salary_estimated_max = data.get("estimated_max")
        db.commit()
        
        # Add timestamp
        data["estimated_at"] = datetime.utcnow().isoformat()
        
        return data
    
    except json.JSONDecodeError as e:
        print(f"Salary estimation JSON parse error: {e}")
        return {"error": "Failed to parse LLM response"}
    except Exception as e:
        print(f"Salary estimation error: {e}")
        return {"error": str(e)}


def _extract_seniority(role_title: str) -> str:
    """Extract seniority level from role title."""
    if not role_title:
        return "Mid-level"
    
    role_lower = role_title.lower()
    
    # Senior+ levels
    if any(keyword in role_lower for keyword in ["principal", "staff", "distinguished", "fellow", "architect"]):
        return "Staff/Principal"
    if any(keyword in role_lower for keyword in ["senior", "sr.", "lead", "tech lead"]):
        return "Senior"
    
    # Junior levels
    if any(keyword in role_lower for keyword in ["junior", "jr.", "entry", "associate", "intern", "graduate"]):
        return "Junior"
    
    # Default to mid-level
    return "Mid-level"


def _get_currency_symbol(currency_code: Optional[str]) -> str:
    """Get currency symbol from code."""
    if not currency_code:
        return "$"
    
    symbols = {
        "USD": "$",
        "INR": "₹",
        "GBP": "£",
        "EUR": "€",
        "CAD": "C$",
        "AUD": "A$",
        "SGD": "S$",
    }
    return symbols.get(currency_code.upper(), "$")


def _infer_currency_from_location(location: str) -> Optional[str]:
    """Infer currency code from location string."""
    if not location or location == "Not specified":
        return None
    
    location_lower = location.lower()
    
    # Indian locations
    if any(city in location_lower for city in [
        "india", "indian", "bengaluru", "bangalore", "mumbai", "bombay", 
        "delhi", "new delhi", "hyderabad", "chennai", "madras", "pune", 
        "kolkata", "calcutta", "ahmedabad", "jaipur", "surat", "lucknow",
        "kanpur", "nagpur", "indore", "thane", "bhopal", "visakhapatnam",
        "pimpri", "patna", "vadodara", "ghaziabad", "ludhiana", "agra",
        "nashik", "faridabad", "meerut", "rajkot", "varanasi", "srinagar",
        "gurgaon", "gurugram", "noida", "kochi", "cochin"
    ]):
        return "INR"
    
    # US locations
    if any(term in location_lower for term in [
        "united states", "usa", "u.s.", "america", "san francisco", "new york",
        "seattle", "austin", "boston", "chicago", "los angeles", "silicon valley",
        "bay area", "washington dc", "miami", "denver", "atlanta", "dallas",
        "houston", "portland", "san diego", "philadelphia", "phoenix"
    ]):
        return "USD"
    
    # UK locations
    if any(term in location_lower for term in [
        "united kingdom", "uk", "u.k.", "britain", "england", "london",
        "manchester", "birmingham", "leeds", "glasgow", "edinburgh", "bristol",
        "liverpool", "cardiff", "belfast", "oxford", "cambridge"
    ]):
        return "GBP"
    
    # European locations
    if any(term in location_lower for term in [
        "germany", "france", "spain", "italy", "netherlands", "belgium",
        "berlin", "munich", "frankfurt", "paris", "lyon", "madrid", "barcelona",
        "rome", "milan", "amsterdam", "brussels", "vienna", "zurich", "geneva",
        "stockholm", "copenhagen", "dublin", "lisbon", "prague", "warsaw"
    ]):
        # Most of Europe uses EUR, but handle exceptions
        if any(term in location_lower for term in ["switzerland", "zurich", "geneva", "bern"]):
            return "USD"  # Swiss Franc not in our list, default to USD equivalent
        if any(term in location_lower for term in ["uk", "britain", "london"]):
            return "GBP"
        return "EUR"
    
    # Canadian locations
    if any(term in location_lower for term in [
        "canada", "canadian", "toronto", "vancouver", "montreal", "ottawa", "calgary"
    ]):
        return "CAD"
    
    # Australian locations
    if any(term in location_lower for term in [
        "australia", "australian", "sydney", "melbourne", "brisbane", "perth", "adelaide"
    ]):
        return "AUD"
    
    # Singapore
    if "singapore" in location_lower:
        return "SGD"
    
    # Default to None if can't determine
    return None
