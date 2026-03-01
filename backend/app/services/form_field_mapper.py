"""Map scraped form fields to profile values using LLM + heuristics."""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Any

from openai import OpenAI

from backend.app.core.config import settings
from backend.app.services.field_normalization import FieldNormalizationService

logger = logging.getLogger(__name__)
_OPENAI_CLIENT: OpenAI | None = None
_MAP_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

MAP_PROMPT = """You are an expert job application autofill assistant with natural language generation capabilities.

Task:
- Map each incoming form field to the best value from candidate data.
- Candidate data includes profile fields, saved custom answers, and resume text.

**FIELD-SPECIFIC RULES:**

1. **NUMERIC FIELDS (years of experience, age, etc.):**
   - Extract ONLY the number from experience data. NEVER return job descriptions or experience paragraphs.
   - "Total Years of Experience" / "Years of Experience" → Return just the number like "2" or "3" (calculate from experience dates)
   - NEVER use profile.experience text for this field - only a single number
   - If experience says "3+ years" or "3 years", return just "3"
   - If it says "5-7 years", return "6" (midpoint)

2. **DROPDOWN/SELECT FIELDS (Gender, Salutation, Yes/No, etc.):**
   - Return EXACT option text as it appears in the dropdown
   - Gender field with options ["Male", "Female", "Other"] → Return exactly "Male" not "male" or "M"
   - Salutation with options ["Mr", "Ms", "Mrs", "Dr"] → Return exactly as shown (check capitalization)
   - For Yes/No dropdowns: Return exactly "Yes" or "No" (capital Y/N)

3. **TEXT FIELDS (textarea, large text, cover letters, descriptions, "why" questions):**
   - DO NOT just copy existing text
   - GENERATE contextual, professional responses based on candidate's profile, experience, and skills
   - For cover letters: Write 2-3 paragraphs highlighting relevant experience and fit
   - For "why do you want to work here" type questions: Generate thoughtful 2-4 sentence responses
   - For compensation/salary questions: Use profile salary data or say "Open to discussion based on market rate and role scope"
   - For descriptions: Summarize relevant experience from resume in 2-3 sentences

4. **COMPANY-SPECIFIC QUESTIONS (current/previous employee, referrals, relationships):**
   - "Are you currently a [company] employee?": Answer "No" UNLESS candidate's current company matches
   - "Have you previously worked at [company]?": Answer "No" UNLESS resume mentions that company
   - "Are you related to anyone at [company]?": Answer "No" or "None"
   - "Do you know anyone at [company]?": If no referral info, say "No" or leave blank

5. **FIRST NAME / LAST NAME (CRITICAL):**
   - "First Name" → Use profile.firstName ONLY, or first word(s) of profile.name. NEVER use full name.
   - "Last Name" → Use profile.lastName ONLY, or last word of profile.name. NEVER use full name.
   - Example: name="Sainath Reddy Guraka" → First="Sainath Reddy", Last="Guraka"

6. **FIELD-SPECIFIC (CRITICAL - never cross-map):**
   - RESUME_FILE → For input type="file" fields labeled Resume/CV/Attach, ALWAYS return RESUME_FILE (client attaches the file). For cover letter file fields, return RESUME_FILE if no cover letter, else null. NEVER use RESUME_FILE for School, Degree, Year, LinkedIn, or any text/select field.
   - "School" / "University" / "College" / "Institution" → Use profile.education school name ONLY. NEVER phone, RESUME_FILE, degree text.
   - "Degree" / "Qualification" → Use degree from education (e.g. "B.Tech", "Bachelor's") ONLY. NEVER RESUME_FILE or phone.
   - "LinkedIn" / "LinkedIn Profile" / "LinkedIn URL" → Use profile.linkedin URL ONLY. NEVER education or experience text.
   - "Phone" / "mobile" / "cell" → Use profile.phone ONLY. Never put phone in School, Degree, Company, Title.
   - "Company name" / "employer" → Use profile.company for first block. For selector/domId ending in -1 use experiences[1].companyName, -2 use experiences[2], etc.
   - "Title" / "job title" → Same pattern: -0 = profile.title or experiences[0].jobTitle, -1 = experiences[1].jobTitle, -2 = experiences[2].jobTitle.
   - "Start date year" / "year" / "graduation year" / "start year" → Return ONLY a 4-digit year like "2025". NEVER RESUME_FILE or education paragraph.
   - "Start date month" / "Start month" → Return month only: "January", "Jan", or "01" depending on options. NEVER a year like "2026".
   - "Current role" (checkbox) → Return "Yes" if most recent job has endDate "Present"/"Current", else "No".
   - "End date month" / "End date year" when current role is ongoing (Present): Use CURRENT month and CURRENT year (e.g. "January", "2025"). Required fields must have values.
   - "Country" → Return country name (e.g. "India"). For dropdowns with "Country+code" format, the system will match "India+91".
   - For ANY dropdown/select: Return EXACTLY one option from the options array. NEVER return a value not in the options list. When options exist, pick the best match from profile/candidate data.
   - "Are you currently a [company] employee?" / "Have you previously worked at [company]?" / "Do you know anyone at [company]?" → Return exactly "Yes" or "No". NEVER education, experience, or long text.
   - Match EACH field by its LABEL and INDEX. Index N must map to the value for field at position N in the fields array.

7. **SIMPLE FIELDS (email, dates):**
   - Use exact profile values
   - For date fields: Format as YYYY-MM-DD or match dropdown (e.g. "Jan", "2025")

8. **YES/NO DEFAULTS (when no explicit info in profile):**
   - Visa/sponsorship, work authorization, relocation, notice period (as Yes/No): Use "No" when absent from profile
   - Language fluency (e.g. Mandarin, other languages): Use "No" when absent
   - These are reasonable defaults for unspecified candidate info

9. **REPEATING BLOCKS (CRITICAL):**
   - Employment: Block -0 = experiences[0], -1 = experiences[1], etc. Map ALL employment blocks from profile.experiences.
   - Education: Block -0 = educations[0], -1 = educations[1], etc. ONLY map blocks where profile.educations[N] exists. If user has 1 education, fill block 0 only; leave blocks 1, 2, etc. as null.

10. **GENERAL:**
   - Never hallucinate hard facts (company names, degree names, years) that are absent from data
   - For optional fields with weak evidence, return null
   - Make all responses natural, professional, and tailored to the field label/context

Output JSON format (use "index" as the key):
{{
  "mappings": {{
    "0": {{
      "value": "string or null",
      "confidence": 0.0,
      "reason": "short explanation"
    }},
    "1": {{ ... }},
    ...
  }}
}}

CRITICAL: Map by INDEX. Field at index 0 gets mappings["0"], index 1 gets mappings["1"], etc. The index is the array position. Do NOT swap values between fields. School gets school name, Degree gets degree, LinkedIn gets URL, Year gets year.

Confidence rules:
- 0.95-1.0 for exact profile/custom-answer matches
- 0.8-0.94 for strong inferred value from resume/profile context or generated text from solid data
- 0.6-0.79 for generated but reasonable answer or intelligent defaults
- <=0.5 when ambiguous or insufficient context

Candidate profile JSON:
{profile_json}

Saved custom answers JSON:
{custom_answers_json}

Resume text (possibly partial):
{resume_text}
"""

# Learning prompt - returns field_fp and profile_key for shared learning
FIELD_MAP_LEARNING_PROMPT = """You are filling a job application form. Given the form fields and the user's profile, return the value to fill for each field.

Return ONLY valid JSON, no markdown, no explanation.

Format:
{{
  "fields": [
    {{
      "field_fp": "<the field_fp you were given>",
      "value": "<value to fill, or empty string if not applicable>",
      "profile_key": "<which profile key you used: first_name|last_name|email|phone|linkedin_url|portfolio_url|address|city|state|zip|country|years_experience|current_title|current_company|salary_expectation|start_date|visa_status|gender|ethnicity|veteran_status|disability_status|cover_letter|null>",
      "confidence": <0.0 to 1.0>
    }}
  ]
}}

Rules:
- If you cannot determine a value from the profile, return value="" and profile_key=null
- For dropdowns (options provided), value MUST be one of the provided options or ""
- EXCEPTION: For School/University/College/Institution fields, if profile.educations[0].institution is not in options, return the institution name anyway (the client uses it for Other+specify flow)
- For Company/Employer dropdowns, if profile.experiences[0].companyName is not in options, return the company name anyway (same fallback)
- For yes/no fields, return "Yes" or "No"
- Never invent values not present in the profile or resume
- You MUST echo back the exact field_fp for each field you were given
- Use the same field-specific rules as the main mapping (First Name, Last Name, School, Degree, etc.)

GENERATE SENSIBLE DEFAULTS for required fields when profile has no explicit value:
- Salary/compensation/target pay: Use profile.expectedSalary if present, else "Open to discussion based on market rate and role scope"
- "Are you currently a [company] employee?": "No" unless current company matches
- "Have you previously worked at [company]?": "No" unless resume mentions that company
- "Are you related to anyone at [company]?": "No" or "None"
- Contractor/agency details (when answer to "previously worked" would be No): "N/A" or "Not applicable"
- Resume/CV file fields: return RESUME_FILE (exact string)
- Cover letter file when no cover letter: return RESUME_FILE or leave ""

User Profile:
{profile_json}

Resume Text:
{resume_text}

Custom Answers:
{custom_answers_json}

Form Fields (each has field_fp - echo it back):
{fields_json}
"""

# Map profile_key from LLM to actual profile dict keys
PROFILE_KEY_TO_FIELD: dict[str, str] = {
    "first_name": "firstName",
    "last_name": "lastName",
    "email": "email",
    "phone": "phone",
    "linkedin_url": "linkedin",
    "portfolio_url": "portfolio",
    "address": "location",
    "city": "city",
    "country": "country",
    "state": "state",
    "zip": "location",
    "years_experience": "experience",
    "current_title": "title",
    "current_company": "company",
    "salary_expectation": "expectedSalary",
    "cover_letter": "professionalSummary",
}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())).strip()


# Common country → "CountryName +Code" for intl-tel-input / country dropdowns when options are truncated
_COUNTRY_OPTION_FALLBACK: dict[str, str] = {
    "india": "India +91",
    "united states": "United States +1",
    "us": "United States +1",
    "usa": "United States +1",
    "united kingdom": "United Kingdom +44",
    "uk": "United Kingdom +44",
    "canada": "Canada +1",
    "australia": "Australia +61",
    "germany": "Germany +49",
    "france": "France +33",
    "japan": "Japan +81",
    "china": "China +86",
    "brazil": "Brazil +55",
    "mexico": "Mexico +52",
    "spain": "Spain +34",
    "italy": "Italy +39",
    "netherlands": "Netherlands +31",
    "south korea": "South Korea +82",
    "indonesia": "Indonesia +62",
    "russia": "Russia +7",
    "saudi arabia": "Saudi Arabia +966",
    "uae": "United Arab Emirates +971",
    "united arab emirates": "United Arab Emirates +971",
    "singapore": "Singapore +65",
    "malaysia": "Malaysia +60",
    "philippines": "Philippines +63",
    "pakistan": "Pakistan +92",
    "bangladesh": "Bangladesh +880",
    "south africa": "South Africa +27",
    "nigeria": "Nigeria +234",
    "egypt": "Egypt +20",
    "ireland": "Ireland +353",
    "new zealand": "New Zealand +64",
    "sweden": "Sweden +46",
    "poland": "Poland +48",
    "switzerland": "Switzerland +41",
    "belgium": "Belgium +32",
    "austria": "Austria +43",
}


def _calculate_years_experience(profile: dict[str, Any]) -> str | None:
    """Calculate total years of experience from profile.experiences or experience text."""
    # First try explicit totalExperience
    total = profile.get("totalExperience") or profile.get("yearsExperience")
    if total is not None:
        match = re.search(r"(\d+)", str(total))
        if match:
            return match.group(1)

    experiences = profile.get("experiences") or []
    if not experiences:
        # Fallback: parse from experience text (e.g. "3+ years" or "Jan 2025-Present")
        exp_text = profile.get("experience") or ""
        match = re.search(r"(\d+)\+?\s*(?:years?|yrs?)?", exp_text, re.I)
        if match:
            return match.group(1)
        # Try to infer from date ranges in text
        year_matches = re.findall(r"\b(19|20)\d{2}\b", exp_text)
        if year_matches:
            years_sorted = sorted(int(y) for y in year_matches)
            return str(max(1, datetime.now().year - years_sorted[0]))
        return None

    total_months = 0
    for exp in experiences:
        start_str = (exp.get("startDate") or exp.get("start_year") or "").strip()
        end_str = (exp.get("endDate") or exp.get("end_year") or "present").strip().lower()
        if not start_str:
            continue
        try:
            start_year = _parse_year_from_date(start_str)
            if start_year is None:
                continue
            if end_str in ("present", "current", "now", ""):
                end_year = datetime.now().year
                end_month = datetime.now().month
            else:
                end_year = _parse_year_from_date(end_str)
                end_month = 6
                if end_year is None:
                    end_year = start_year + 1
            start_month = _parse_month_from_date(start_str) or 1
            total_months += max(0, (end_year - start_year) * 12 + (end_month - start_month))
        except (TypeError, ValueError):
            continue
    if total_months > 0:
        years = max(1, round(total_months / 12))
        return str(years)
    return None


def _parse_year_from_date(s: str) -> int | None:
    """Extract 4-digit year from date string like 'Jan 2025', '2025', '04/2023'."""
    if not s:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", str(s))
    return int(match.group(0)) if match else None


def _parse_month_from_date(s: str) -> int | None:
    """Extract month (1-12) from date string like 'Jan 2025', 'January 2025'."""
    if not s:
        return None
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
              "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    for name, num in months.items():
        if name in str(s).lower():
            return num
    return None


def _field_key(field: dict[str, Any]) -> str:
    """Use index as primary key for consistent client lookups (mappings[field.index])."""
    idx = field.get("index")
    if idx is not None and idx != "":
        return str(idx)
    if field.get("id"):
        return str(field["id"])
    return str(field.get("index", ""))


def _combined_field_text(field: dict[str, Any]) -> str:
    return _norm(" ".join(
        str(field.get(k, "") or "")
        for k in ("label", "name", "id", "placeholder", "type", "normalized_key")
    ))


def _get_openai_client() -> OpenAI:
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        _OPENAI_CLIENT = OpenAI(api_key=settings.openai_api_key)
    return _OPENAI_CLIENT


def _build_cache_key(
    fields: list[dict[str, Any]],
    profile: dict[str, Any],
    custom_answers: dict[str, str],
    resume_text: str,
) -> str:
    payload = {
        "fields": fields,
        "profile": profile,
        "custom_answers": custom_answers,
        "resume_text": resume_text,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _cache_get(cache_key: str) -> dict[str, Any] | None:
    cached = _MAP_CACHE.get(cache_key)
    if not cached:
        return None
    cached_at, mappings = cached
    if (time.time() - cached_at) > settings.form_field_cache_ttl:
        _MAP_CACHE.pop(cache_key, None)
        return None
    return mappings


def _cache_put(cache_key: str, mappings: dict[str, Any]) -> None:
    if len(_MAP_CACHE) >= settings.form_field_cache_max_entries:
        oldest_key = min(_MAP_CACHE.items(), key=lambda item: item[1][0])[0]
        _MAP_CACHE.pop(oldest_key, None)
    _MAP_CACHE[cache_key] = (time.time(), mappings)


def _empty_mapping(key: str) -> dict[str, Any]:
    """Return empty mapping for a field."""
    return {"value": None, "confidence": 0.5, "reason": "No mapping"}


def _is_education_like(value: str) -> bool:
    """Detect if value looks like education text (B.Tech, degree, university, etc.)."""
    if not value:
        return False
    v = str(value).lower()
    edu_keywords = ("b.tech", "btech", "m.tech", "mtech", "bachelor", "degree", "university", "college", "engineering", "computer science", "aug ", "apr ")
    if any(kw in v for kw in edu_keywords):
        return True
    if len(v.strip()) >= 20 and any(kw in v for kw in ("in ", " and ", "from ")):
        return True
    return False


def _is_year_only_field(field_label: str, field_text: str) -> bool:
    """Detect if field expects only a year (e.g. Start date year)."""
    lbl = field_label.lower()
    txt = field_text.lower()
    return "year" in lbl or "year" in txt or ("start" in lbl and "date" in lbl) or ("date" in lbl and "start" in txt)


def _is_yes_no_employee_question(field_label: str, field_text: str) -> bool:
    """Detect company-specific yes/no questions (employee, worked at, etc.)."""
    combined = (field_label + " " + field_text).lower()
    return (
        "are you currently" in combined or "are you a " in combined or "currently a " in combined
        or "previously worked" in combined or "worked at" in combined or "have you previously" in combined
        or "do you know anyone" in combined or "know anyone at" in combined
        or "employee?" in combined or "if \"yes\"" in combined or "if \"no\"" in combined
    )


def _is_school_or_degree_field(field_label: str, field_text: str) -> bool:
    """Detect School/University/Degree fields - must receive education data only."""
    combined = (field_label + " " + field_text).lower()
    school_kw = "school" in combined or "university" in combined or "college" in combined or "institution" in combined
    degree_kw = "degree" in combined or "qualification" in combined
    return school_kw or degree_kw


def _is_linkedin_field(field_label: str, field_text: str) -> bool:
    """Detect LinkedIn URL field - must receive URL only, not education/experience."""
    combined = (field_label + " " + field_text).lower()
    return "linkedin" in combined and ("url" in combined or "profile" in combined or "link" in combined)


def _looks_like_phone(value: str) -> bool:
    """Value is likely a phone number (e.g. 9676688586)."""
    s = re.sub(r"[\s\-\(\)\.]", "", str(value or ""))
    return len(s) >= 9 and s.isdigit()


def _looks_like_email(value: str) -> bool:
    """Value looks like an email address."""
    s = str(value or "").strip()
    return "@" in s and "." in s and len(s) > 5


def _looks_like_name(value: str) -> bool:
    """Value looks like a person name (not a number, not email)."""
    s = str(value or "").strip()
    if not s or len(s) > 80:
        return False
    if _looks_like_phone(s) or _looks_like_email(s) or s.isdigit():
        return False
    # Names typically have letters and maybe spaces
    return bool(re.match(r"^[a-zA-Z\s\-\.]+$", s))


def _looks_like_location(value: str) -> bool:
    """Value looks like location (city, country, address)."""
    s = str(value or "").strip().lower()
    if "," in s and any(kw in s for kw in ("india", "usa", "uk", "city", "bangalore", "london")):
        return True
    return "(" in s and "+" in s  # e.g. "India (+91)"


def _clean_field_value(
    field: dict[str, Any],
    mapping: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value = mapping.get("value")
    if value is None or value == "":
        return mapping
    field_label = str(field.get("label", "")).lower()
    field_type = str(field.get("type", "")).lower()
    field_text = _norm(" ".join([str(field.get(k, "")) for k in ("label", "name", "placeholder")]))
    value_str = str(value).strip()

    if value == "RESUME_FILE" and field_type != "file" and "resume" not in field_text and "cv" not in field_text:
        return {"value": None, "confidence": 0.0, "reason": "RESUME_FILE only for file upload fields"}
    # Email: reject Yes/No and non-email values
    if ("email" in field_text or "e-mail" in field_text) and value not in (None, "", "RESUME_FILE"):
        if str(value).strip().lower() in ("yes", "no"):
            return {"value": None, "confidence": 0.0, "reason": "Email field must not receive Yes/No"}
        if not _looks_like_email(value_str) and len(value_str) > 3:
            return {"value": None, "confidence": 0.0, "reason": "Email field received non-email value"}
    # Phone country code vs full number: country code dropdown gets "Country +N", number field gets digits only
    field_sel = str(field.get("selector") or field.get("domId") or "").lower()
    field_name = str(field.get("name") or "").lower()
    is_country_code_field = (
        "country-codes" in field_sel or "country-code" in field_sel or "countrycode" in field_name
        or "country code" in field_label
    )
    if is_country_code_field and _looks_like_phone(value_str):
        profile_country = (profile or {}).get("country") or ""
        country_key = str(profile_country).strip().lower()
        country_option = _COUNTRY_OPTION_FALLBACK.get(country_key)
        if country_option:
            return {
                "value": country_option,
                "confidence": 0.95,
                "reason": f"Phone country code from profile.country: {country_option}",
            }
    # Phone: reject location-like values
    if ("phone" in field_text or "mobile" in field_text or "cell" in field_text or "telephone" in field_text) and value:
        if _looks_like_location(value_str):
            return {"value": None, "confidence": 0.0, "reason": "Phone field must not receive location"}
        if _looks_like_name(value_str) and not _looks_like_phone(value_str):
            return {"value": None, "confidence": 0.0, "reason": "Phone field must not receive name"}
    # Postal/Zip: reject name-like values
    if ("postal" in field_text or "zip" in field_text or "postcode" in field_text) and value:
        if _looks_like_name(value_str):
            return {"value": None, "confidence": 0.0, "reason": "Postal field must not receive name"}
        if _looks_like_location(value_str):
            return {"value": None, "confidence": 0.0, "reason": "Postal field must not receive location"}
    # School/Degree: reject phone numbers and RESUME_FILE
    if _is_school_or_degree_field(field_label, field_text):
        if value == "RESUME_FILE":
            return {"value": None, "confidence": 0.0, "reason": "School/Degree must not receive RESUME_FILE"}
        if _looks_like_phone(value_str):
            return {"value": None, "confidence": 0.0, "reason": "School/Degree must not receive phone number"}
    # LinkedIn: reject education/experience text; use profile.linkedin when available
    if _is_linkedin_field(field_label, field_text) and _is_education_like(value_str):
        linkedin = (profile or {}).get("linkedin")
        if linkedin and str(linkedin).strip().startswith(("http", "linkedin.com", "www.")):
            return {"value": linkedin, "confidence": 0.9, "reason": "LinkedIn field received education; used profile.linkedin"}
        return {"value": None, "confidence": 0.0, "reason": "LinkedIn field must receive URL, not education text"}
    # Year/date fields: reject education text, extract year or use reasonable default
    if _is_year_only_field(field_label, field_text) and _is_education_like(str(value)):
        year_match = re.search(r"\b(19|20)\d{2}\b", str(value))
        if year_match:
            return {
                "value": year_match.group(0),
                "confidence": 0.85,
                "reason": "Extracted year from misplaced education text",
            }
        return {"value": None, "confidence": 0.0, "reason": "Year field received education text; no year found"}
    # Yes/no employee questions: must be Yes or No only; use "No" when LLM sent wrong type
    if _is_yes_no_employee_question(field_label, field_text) and _is_education_like(str(value)):
        return {
            "value": "No",
            "confidence": 0.85,
            "reason": "Yes/no question received education text; defaulting to No",
        }
    if value and value != "RESUME_FILE" and re.match(r"^\d{8,}$", str(value).strip()):
        if "company" in field_text or "employer" in field_text or ("title" in field_text and "job" in field_text):
            return {"value": None, "confidence": 0.0, "reason": "Phone number does not belong in company/title field"}
    if "experience" in field_label and ("year" in field_label or "years" in field_label):
        if isinstance(value, str) and len(value) > 50:
            # Long text wrongly mapped - calculate from profile
            years_val = _calculate_years_experience(profile or {})
            if years_val:
                return {
                    "value": years_val,
                    "confidence": 0.9,
                    "reason": "Extracted years from profile (field received experience text)",
                }
            match = re.search(r"(\d+)\+?\s*(?:years?|yrs?)?", value, re.I)
            if match:
                return {
                    "value": match.group(1),
                    "confidence": mapping.get("confidence", 0.9),
                    "reason": f"Extracted number from: {value[:50]}...",
                }
        elif isinstance(value, str):
            match = re.search(r"(\d+)\+?\s*(?:years?|yrs?)?", value, re.I)
            if match:
                return {
                    "value": match.group(1),
                    "confidence": mapping.get("confidence", 0.9),
                    "reason": f"Extracted number from: {value}",
                }
    if field_type in ("select", "combobox") and field.get("options"):
        options = [o for o in field["options"] if o and str(o).strip()]
        value_str = str(value).strip()
        val_lower = value_str.lower()
        field_lower = field_label + " " + field_text
        # Exact match
        if value_str in options:
            return mapping

        def _norm_apostrophe(s: str) -> str:
            return str(s).replace("\u2019", "'").replace("\u2018", "'").lower()

        for option in options:
            if option.lower() == val_lower or _norm_apostrophe(option) == _norm_apostrophe(value_str):
                return {
                    "value": option,
                    "confidence": mapping.get("confidence", 0.95),
                    "reason": f"Matched to dropdown option: {option}"
                }
        # For country: prefer options that START with country name (India+91 not British Indian Ocean Territory+246)
        if "country" in field_lower and val_lower:
            for option in options:
                opt_lower = str(option).lower()
                if opt_lower.startswith(val_lower) or opt_lower.startswith(val_lower + "+"):
                    return {
                        "value": option,
                        "confidence": mapping.get("confidence", 0.95),
                        "reason": f"Country prefix match: {option}"
                    }
            for option in options:
                if val_lower in opt_lower and not any(
                    x in opt_lower for x in ["territory", "ocean", "island", "virgin", "samoa"]
                ):
                    return {
                        "value": option,
                        "confidence": mapping.get("confidence", 0.9),
                        "reason": f"Country match: {option}"
                    }
        # Partial / contains match (general)
        # For country: never accept options where val is substring but option contains territory/ocean etc (India ≠ British Indian Ocean Territory)
        excluded_substrings = ("territory", "ocean", "island", "virgin", "samoa")
        for option in options:
            opt_lower = str(option).lower()
            if val_lower in opt_lower or opt_lower in val_lower:
                if "country" in field_lower and len(val_lower) < 15:
                    if any(x in opt_lower for x in excluded_substrings):
                        continue
                return {
                    "value": option,
                    "confidence": mapping.get("confidence", 0.85),
                    "reason": f"Partial match to dropdown option: {option}"
                }
        # Country fallback: options may be truncated (e.g. 100 items); use lookup for common countries
        if "country" in field_lower and val_lower:
            constructed = _COUNTRY_OPTION_FALLBACK.get(val_lower)
            if constructed:
                if constructed in options:
                    return {
                        "value": constructed,
                        "confidence": mapping.get("confidence", 0.95),
                        "reason": f"Country fallback match: {constructed}",
                    }
                return {
                    "value": constructed,
                    "confidence": 0.9,
                    "reason": f"Country fallback (options truncated): {constructed}",
                }
        # School/Institution/College: when value not in closed list, try "Other"/"Not listed" or return raw value
        if any(kw in field_lower for kw in ("school", "university", "college", "institution")):
            other_opts = [
                o for o in options
                if re.search(r"\bother\b|not\s*listed|not\s*in\s*list|my\s*school\s*is|specify|please\s*specify|_other|other\s*[\(\-\:]", str(o).lower())
            ]
            if other_opts:
                return {
                    "value": other_opts[0],
                    "confidence": 0.75,
                    "reason": "Institution not in dropdown; selected 'Other/Not listed'",
                }
            # Best partial match: option containing most significant words from value (e.g. "Nehru" in "JNU")
            val_words = set(re.findall(r"\b[a-z]{4,}\b", val_lower)) - {"university", "college", "institute", "school", "of", "the", "and"}
            if val_words:
                best = None
                best_score = 0
                for opt in options:
                    opt_lower = str(opt).lower()
                    opt_words = set(re.findall(r"\b[a-z]{4,}\b", opt_lower))
                    overlap = len(val_words & opt_words)
                    if overlap > best_score and overlap >= 1:
                        best_score = overlap
                        best = opt
                if best:
                    return {
                        "value": best,
                        "confidence": 0.7,
                        "reason": f"Partial word match: {best}",
                    }
            # No match and no "Other": return raw institution so client can use for Other+specify flow
            if value_str and len(value_str) > 2:
                return {
                    "value": value_str,
                    "confidence": 0.7,
                    "reason": "Institution not in dropdown; returning raw value for Other/specify flow",
                }
        # Company/Employer: same fallback when value not in options
        if any(kw in field_lower for kw in ("company", "employer", "organization")):
            other_opts = [
                o for o in options
                if re.search(r"\bother\b|not\s*listed|specify|please\s*enter|company\s*name|employer", str(o).lower())
            ]
            if other_opts:
                return {"value": other_opts[0], "confidence": 0.75, "reason": "Company not in dropdown; selected Other"}
            if value_str and len(value_str) > 2:
                return {
                    "value": value_str,
                    "confidence": 0.7,
                    "reason": "Company not in dropdown; returning raw value for Other/specify flow",
                }
        # No option matches the LLM value — nullify so the field is skipped/highlighted
        return {
            "value": None,
            "confidence": 0.0,
            "reason": f"LLM value '{value_str}' not found in dropdown options"
        }
    return mapping


def _normalize_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    processed_fields = []
    for field in fields:
        normalized = field.copy()
        norm_key = FieldNormalizationService.normalize(
            label=field.get("label", ""),
            name=field.get("name", ""),
            field_id=field.get("id", ""),
        )
        if norm_key:
            normalized["normalized_key"] = norm_key
        processed_fields.append(normalized)
    return processed_fields


def map_form_fields(
    fields: list[dict[str, Any]],
    profile: dict[str, Any],
    custom_answers: dict[str, str] | None = None,
    resume_text: str | None = None,
) -> dict[str, Any]:
    started_at = time.monotonic()
    if not fields:
        return {}

    logger.info(
        "Field mapping requested fields=%d profile_keys=%d custom_answers=%d resume_text_len=%d",
        len(fields),
        len(profile or {}),
        len(custom_answers or {}),
        len((resume_text or "")),
    )
    logger.info(
        "Scraped fields preview (idx|label|type|required): %s",
        [(f.get("index"), (f.get("label") or f.get("name") or "?")[:40], f.get("type"), f.get("required")) for f in (fields or [])[:15]],
    )

    custom_answers = custom_answers or {}
    resume_text = (resume_text or "").strip()[:4000]  # Reduced for faster LLM processing
    processed_fields = _normalize_fields(fields)

    cache_key = _build_cache_key(processed_fields, profile or {}, custom_answers, resume_text)
    cached_mapping = _cache_get(cache_key)
    if cached_mapping is not None:
        logger.info("Field mapping cache hit fields=%d", len(processed_fields))
        return cached_mapping

    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY missing; returning empty mappings")
        return {str(_field_key(f)): _empty_mapping(str(_field_key(f))) for f in processed_fields}

    logger.info("LLM mapping: sending %d fields to LLM", len(processed_fields))

    client = _get_openai_client()
    profile_desc = json.dumps(profile or {}, separators=(",", ":"))
    custom_answers_desc = json.dumps(custom_answers, separators=(",", ":"))
    prompt = MAP_PROMPT.format(
        profile_json=profile_desc,
        custom_answers_json=custom_answers_desc,
        resume_text=resume_text or "No resume text provided.",
    )

    # Send minimal field payload (index, label, type, options, selector/domId for block inference)
    llm_fields_minimal = []
    for f in processed_fields:
        item = {
            "index": f.get("index"),
            "label": (f.get("label") or f.get("name") or "")[:80],
            "type": f.get("type"),
            "options": (f.get("options") or [])[:30],
        }
        sel = f.get("selector") or f.get("domId") or ""
        if sel:
            item["selector"] = sel[:60]
        llm_fields_minimal.append(item)
    fields_desc = json.dumps(llm_fields_minimal, separators=(",", ":"))

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Form fields:\n{fields_desc}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=2048,
    )

    content = response.choices[0].message.content or "{}"
    try:
        payload = json.loads(content)
        llm_mappings = payload.get("mappings", {})
        logger.info(
            "LLM response parsed llm_mapping_keys=%d sample=%s",
            len(llm_mappings) if isinstance(llm_mappings, dict) else 0,
            json.dumps({k: v for k, v in list((llm_mappings or {}).items())[:3]}, indent=2) if isinstance(llm_mappings, dict) else "N/A"
        )
    except json.JSONDecodeError:
        logger.warning("LLM mapping response was invalid JSON")
        llm_mappings = {}

    merged: dict[str, Any] = {}
    for field in processed_fields:
        key = str(_field_key(field))
        llm_value = llm_mappings.get(key) if isinstance(llm_mappings, dict) else None
        if isinstance(llm_value, dict) and "value" in llm_value:
            merged[key] = _clean_field_value(field, llm_value, profile)
        else:
            merged[key] = _empty_mapping(key)

    elapsed_ms = int((time.monotonic() - started_at) * 1000)
    logger.info(
        "Field mapping completed fields=%d merged_keys=%d elapsed_ms=%d",
        len(processed_fields),
        len(merged),
        elapsed_ms,
    )
    logger.info(
        "Mappings preview: %s",
        [(k, str((v or {}).get("value", ""))[:25]) for k, v in list(merged.items())[:15]],
    )
    _cache_put(cache_key, merged)
    return merged


def map_form_fields_llm_for_misses(
    fields_with_fp: list[dict[str, Any]],
    profile: dict[str, Any],
    custom_answers: dict[str, str] | None = None,
    resume_text: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    LLM mapping for learning flow - returns results keyed by field_fp.
    Each field in fields_with_fp must have "_fp" set.
    """
    if not fields_with_fp or not settings.openai_api_key:
        return {}

    custom_answers = custom_answers or {}
    resume_text = (resume_text or "").strip()[:4000]
    client = _get_openai_client()

    llm_fields = []
    for f in fields_with_fp:
        fp = f.get("_fp", "")
        if not fp:
            continue
        llm_fields.append({
            "field_fp": fp,
            "label": (f.get("label") or f.get("name") or "")[:80],
            "type": f.get("type"),
            "options": (f.get("options") or [])[:30],
        })

    if not llm_fields:
        return {}

    prompt = FIELD_MAP_LEARNING_PROMPT.format(
        profile_json=json.dumps(profile or {}, separators=(",", ":")),
        resume_text=resume_text or "No resume text provided.",
        custom_answers_json=json.dumps(custom_answers, separators=(",", ":")),
        fields_json=json.dumps(llm_fields, separators=(",", ":")),
    )

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Map these form fields."},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2048,
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        raw_fields = payload.get("fields", [])

        result: dict[str, dict[str, Any]] = {}
        fp_to_field = {f["_fp"]: f for f in fields_with_fp if f.get("_fp")}
        for item in raw_fields:
            fp = item.get("field_fp")
            if not fp or fp not in fp_to_field:
                continue
            field = fp_to_field[fp]
            value = item.get("value")
            profile_key = item.get("profile_key")
            confidence = float(item.get("confidence", 0.8))
            cleaned = _clean_field_value(field, {"value": value, "confidence": confidence}, profile)
            result[fp] = {
                "value": cleaned.get("value"),
                "confidence": cleaned.get("confidence", 0.8),
                "profile_key": profile_key,
                "reason": cleaned.get("reason", ""),
            }
        return result
    except Exception as e:
        logger.warning("LLM learning mapping failed: %s", e)
        return {}
