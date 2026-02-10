"""
Resume extraction using pdfplumber - parses PDF text into profile schema
"""
import re
from pathlib import Path
from typing import List, Tuple

import pdfplumber

from backend.app.schemas.profile import (
    Education,
    Experience,
    Links,
    ProfilePayload,
    SoftSkill,
    TechSkill,
)


def extract_text_from_pdf(file_path: str | Path) -> str:
    """Extract raw text from PDF using pdfplumber."""
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_email(text: str) -> str:
    """Extract first email from text."""
    match = re.search(r"[\w.+-]+@[\w.-]+\.\w{2,}", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    """Extract first phone number from text."""
    patterns = [
        r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        r"\d{3}[-.\s]\d{3}[-.\s]\d{4}",
        r"\+?\d{10,15}",
    ]
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            return match.group(0).strip()
    return ""


def extract_urls(text: str) -> dict:
    """Extract LinkedIn, GitHub, portfolio URLs from text."""
    url_pattern = r"https?://[^\s<>\"'\]]+"
    urls = re.findall(url_pattern, text)
    result = {"linkedInUrl": "", "githubUrl": "", "portfolioUrl": "", "otherLinks": []}
    for url in urls:
        url_clean = url.rstrip(".,;:)")
        url_lower = url_clean.lower()
        if "linkedin.com" in url_lower and not result["linkedInUrl"]:
            result["linkedInUrl"] = url_clean
        elif "github.com" in url_lower and not result["githubUrl"]:
            result["githubUrl"] = url_clean
        elif any(x in url_lower for x in ["portfolio", "personal", "website", ".me"]) and not result["portfolioUrl"]:
            result["portfolioUrl"] = url_clean
    return result


def extract_urls_from_pdf(file_path: str | Path) -> dict:
    """Extract LinkedIn, GitHub, portfolio URLs from PDF hyperlink annotations (clickable links)."""
    result = {"linkedInUrl": "", "githubUrl": "", "portfolioUrl": "", "otherLinks": []}
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                for link in getattr(page, "hyperlinks", []) or []:
                    uri = link.get("uri") or ""
                    if not uri or not uri.startswith("http"):
                        continue
                    uri_clean = uri.strip()
                    url_lower = uri_clean.lower()
                    if "linkedin.com" in url_lower and not result["linkedInUrl"]:
                        result["linkedInUrl"] = uri_clean
                    elif "github.com" in url_lower and not result["githubUrl"]:
                        result["githubUrl"] = uri_clean
                    elif any(x in url_lower for x in ["portfolio", "personal", "website", ".me"]) and not result["portfolioUrl"]:
                        result["portfolioUrl"] = uri_clean
    except Exception:
        pass
    return result


def _merge_urls(from_text: dict, from_pdf: dict) -> dict:
    """Merge URL dicts: use non-empty from either source for LinkedIn, GitHub, portfolio."""
    return {
        "linkedInUrl": from_text.get("linkedInUrl") or from_pdf.get("linkedInUrl") or "",
        "githubUrl": from_text.get("githubUrl") or from_pdf.get("githubUrl") or "",
        "portfolioUrl": from_text.get("portfolioUrl") or from_pdf.get("portfolioUrl") or "",
        "otherLinks": list(from_text.get("otherLinks") or []),
    }


def extract_section(text: str, section_names: list[str]) -> str:
    """Extract content under a section header until next section or end."""
    lines = text.split("\n")
    section_pattern = re.compile(
        r"^(" + "|".join(re.escape(s) for s in section_names) + r")\s*:?\s*$",
        re.IGNORECASE,
    )
    in_section = False
    content_lines = []
    end_sections = [
        "experience", "education", "skills", "projects", "summary", "objective",
        "certifications", "references", "contact", "work history", "employment",
    ]
    end_pattern = re.compile(
        r"^\s*(" + "|".join(re.escape(s) for s in end_sections) + r")\s*:?\s*$",
        re.IGNORECASE,
    )

    for line in lines:
        if section_pattern.match(line.strip()):
            in_section = True
            continue
        if in_section:
            if end_pattern.match(line.strip()) and not any(s in line.lower() for s in section_names):
                break
            if line.strip():
                content_lines.append(line.strip())
    return "\n".join(content_lines)


def extract_experiences(text: str) -> List[Experience]:
    """Extract work experience entries from text."""
    section = extract_section(text, [
        "experience", "work experience", "work history", "employment", "professional experience",
    ])
    if not section:
        return []

    experiences = []
    lines = section.split("\n")
    current = None

    # Look for date patterns (e.g. 2020-2023, Jan 2020 - Present, 01/2020 - 06/2023)
    date_pattern = re.compile(
        r"(\d{1,2}/?\d{0,2}/?\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4})\s*[-–—to]+\s*"
        r"(Present|Current|\d{1,2}/?\d{0,2}/?\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4})",
        re.IGNORECASE,
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        date_match = date_pattern.search(line)
        if date_match:
            if current and current.get("jobTitle"):
                experiences.append(current)
            # Assume structure: Job Title at Company | Date range
            parts = line.split("|") if "|" in line else [line]
            title_company = (parts[0] if parts else line).strip()
            date_str = date_match.group(0)
            # Try to split title and company
            at_idx = title_company.lower().find(" at ")
            if at_idx > 0:
                title = title_company[:at_idx].strip()
                company = title_company[at_idx + 4 :].strip()
            else:
                title = title_company
                company = ""
            current = {
                "jobTitle": title,
                "companyName": company,
                "startDate": date_match.group(1),
                "endDate": date_match.group(2) or "",
                "employmentType": "",
                "location": "",
                "workMode": "",
                "description": "",
                "techStack": "",
            }
        elif current:
            if not current.get("description"):
                current["description"] = line
            else:
                current["description"] += " " + line
        i += 1

    if current:
        experiences.append(current)

    # If no date-based parsing worked, try bullet-based
    if not experiences and section:
        entries = re.split(r"\n(?=[•\-\*]\s|\d+\.\s)", section)
        for entry in entries[:5]:  # Limit to 5
            entry = entry.strip().strip("•-*").strip()
            if len(entry) > 20:
                experiences.append({
                    "jobTitle": entry[:80],
                    "companyName": "",
                    "description": entry,
                    "employmentType": "",
                    "startDate": "",
                    "endDate": "",
                    "location": "",
                    "workMode": "",
                    "techStack": "",
                })

    return [Experience(**e) for e in experiences]


def extract_educations(text: str) -> List[Education]:
    """Extract education entries from text."""
    section = extract_section(text, [
        "education", "academic", "academics", "qualification", "qualifications",
    ])
    if not section:
        return []

    educations = []
    lines = [l.strip() for l in section.split("\n") if l.strip()]
    year_pattern = re.compile(r"\b(19|20)\d{2}\b")

    i = 0
    while i < len(lines):
        line = lines[i]
        years = year_pattern.findall(line) or []
        if years or "degree" in line.lower() or "b." in line.lower() or "m." in line.lower():
            degree = line
            institution = lines[i + 1] if i + 1 < len(lines) else ""
            if institution and len(institution) > 2:
                i += 1
            year_match = year_pattern.search(line)
            start_year = year_match.group(0) if year_match else ""
            educations.append(Education(
                degree=degree[:100],
                fieldOfStudy="",
                institution=institution[:100] if institution else "",
                startYear=start_year,
                endYear="",
                grade="",
                location="",
            ))
        i += 1

    if not educations and section:
        for line in lines[:3]:
            if len(line) > 5:
                educations.append(Education(degree=line[:100], institution="", fieldOfStudy="", startYear="", endYear="", grade="", location=""))

    return educations


def extract_skills(text: str) -> Tuple[List[TechSkill], List[SoftSkill]]:
    """Extract tech and soft skills from text."""
    section = extract_section(text, [
        "skills", "technical skills", "technologies", "expertise", "core competencies",
        "programming", "tools", "tech stack",
    ])
    if not section:
        section = text  # Fallback: scan full text

    tech_skills = []
    soft_skills = []
    tech_keywords = [
        "python", "javascript", "java", "react", "node", "sql", "aws", "docker",
        "git", "html", "css", "typescript", "angular", "vue", "postgresql", "mongodb",
        "linux", "rest", "api", "agile", "scrum", "figma", "azure", "gcp",
    ]

    # Split by common separators
    tokens = re.split(r"[,;•\|\n/]", section)
    seen = set()
    for t in tokens:
        t = t.strip()
        if len(t) < 2 or len(t) > 50:
            continue
        t_lower = t.lower()
        if t_lower in seen:
            continue
        if any(kw in t_lower for kw in tech_keywords):
            seen.add(t_lower)
            tech_skills.append(TechSkill(name=t, level="", years=""))
        elif t and not re.match(r"^\d+$", t):
            seen.add(t_lower)
            soft_skills.append(SoftSkill(name=t))

    return tech_skills, soft_skills


def extract_summary(text: str) -> str:
    """Extract professional summary/objective."""
    section = extract_section(text, [
        "summary", "professional summary", "objective", "profile", "about",
    ])
    return section[:800] if section else ""


def extract_name(text: str) -> Tuple[str, str]:
    """Extract first and last name from top of resume."""
    lines = [l.strip() for l in text.split("\n") if l.strip()][:5]
    for line in lines:
        if "@" in line or re.search(r"\d{3}[-.\s]\d{3}", line):
            continue
        parts = line.split()
        if 1 <= len(parts) <= 4 and all(p[0].isupper() or not p.isalpha() for p in parts if p):
            if len(parts) >= 2:
                return parts[0], " ".join(parts[1:])
            return parts[0], ""
    return "", ""


# Words that must NOT be treated as city or country (tech/skills/languages)
_LOCATION_BLOCKLIST = frozenset({
    "javascript", "python", "typescript", "java", "react", "node", "sql", "html", "css",
    "mongodb", "postgresql", "aws", "docker", "git", "angular", "vue", "linux", "rest",
    "api", "agile", "scrum", "figma", "azure", "gcp", "express", "next", "redux",
    "languages", "skills", "technologies", "frontend", "backend", "full", "stack",
    "interests", "summary", "experience", "education", "projects", "certifications",
})
# Sentence/description words – if these appear, treat as wrong and return empty
_LOCATION_SENTENCE_WORDS = frozenset({
    "developed", "increasing", "engagement", "applications", "scalable", "user",
    "building", "dynamic", "experience", "integrated", "implemented", "optimization",
    "fixed", "built", "used", "handling", "improve", "enhance", "delivering",
})


def _looks_like_place(part: str) -> bool:
    """True if this string could be a city/country name (not tech/skill or sentence fragment)."""
    if not part or len(part) > 40:
        return False
    # Reject sentence fragments: " by ", " by 30%", ". ", leading period
    part_clean = part.strip()
    if part_clean.startswith(".") or " by " in part_clean.lower() or "%" in part_clean:
        return False
    if ". " in part_clean and part_clean.index(". ") < len(part_clean) - 2:
        return False
    clean = part_clean.split(":")[-1].strip()
    clean = re.sub(r"\s*\d+\s*", "", clean)
    if not clean:
        return False
    token = clean.split(",")[0].strip().lower()
    if token in _LOCATION_BLOCKLIST:
        return False
    if any(block in token for block in _LOCATION_BLOCKLIST):
        return False
    if any(w in token for w in _LOCATION_SENTENCE_WORDS):
        return False
    return True


def extract_location(text: str) -> Tuple[str, str]:
    """Extract city and country from text. Returns empty when not clearly a location (never wrong)."""
    # 1) Only use explicit Location / Address / Contact section
    location_section = extract_section(text, [
        "location", "address", "city", "contact", "contact information", "based in",
    ])
    if location_section:
        lines = [l.strip() for l in location_section.split("\n") if l.strip()]
        for line in lines[:5]:
            if ":" in line:
                line = line.split(":", 1)[-1].strip()
            if "," in line:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 2:
                    city_cand, country_cand = parts[0], parts[-1]
                    if _looks_like_place(city_cand) and _looks_like_place(country_cand):
                        return city_cand, country_cand
            if line and _looks_like_place(line) and not re.search(r"[\w.+-]+@[\w.-]+\.\w{2,}", line):
                return line, ""

    # 2) Only scan top 10 lines and require SHORT place-like parts (avoid bullet/description text)
    lines = text.split("\n")[:10]
    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        if not line_stripped or len(line_stripped) > 60:
            continue
        if "languages" in line_lower or "skills" in line_lower or "technologies" in line_lower:
            continue
        if any(kw in line_lower for kw in ("javascript", "python", "typescript", "react", "node")):
            continue
        if any(w in line_lower for w in _LOCATION_SENTENCE_WORDS):
            continue
        if "," in line_stripped and re.search(r"[A-Za-z][a-z]+,\s*[A-Za-z][a-z]+", line_stripped):
            parts = [p.strip() for p in line_stripped.split(",")]
            if len(parts) >= 2:
                city_cand = parts[0].strip()
                country_cand = parts[-1].strip()
                if len(city_cand) <= 35 and len(country_cand) <= 35 and _looks_like_place(city_cand) and _looks_like_place(country_cand):
                    return city_cand, country_cand
    return "", ""


def extract_resume_to_payload(
    file_path: str | Path,
    resume_url: str | None = None,
    resume_last_updated: str | None = None,
) -> ProfilePayload:
    """Extract resume data from PDF and return ProfilePayload."""
    try:
        text = extract_text_from_pdf(file_path)
    except Exception:
        text = ""

    if not text.strip():
        return ProfilePayload(
            resumeUrl=resume_url,
            resumeLastUpdated=resume_last_updated,
        )

    first_name, last_name = extract_name(text)
    email = extract_email(text)
    phone = extract_phone(text)
    city, country = extract_location(text)
    urls_from_text = extract_urls(text)
    urls_from_pdf = extract_urls_from_pdf(file_path)
    urls = _merge_urls(urls_from_text, urls_from_pdf)
    summary = extract_summary(text)
    experiences = extract_experiences(text)
    educations = extract_educations(text)
    tech_skills, soft_skills = extract_skills(text)

    return ProfilePayload(
        resumeUrl=resume_url,
        resumeLastUpdated=resume_last_updated,
        firstName=first_name,
        lastName=last_name,
        email=email,
        phone=phone,
        city=city,
        country=country,
        professionalSummary=summary[:800],
        professionalHeadline=summary[:120] if summary else "",
        experiences=experiences,
        educations=educations,
        techSkills=tech_skills,
        softSkills=soft_skills,
        links=Links(
            linkedInUrl=urls.get("linkedInUrl", ""),
            githubUrl=urls.get("githubUrl", ""),
            portfolioUrl=urls.get("portfolioUrl", ""),
            otherLinks=[],
        ),
    )
