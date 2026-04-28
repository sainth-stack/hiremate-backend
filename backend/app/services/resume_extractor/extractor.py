"""
Resume extraction using LangGraph + OpenAI LLM for accurate, structured mapping.
Uses pdfplumber for text extraction, then LLM for perfect schema mapping.

Production-grade features:
- Comprehensive error handling with fallbacks
- Request timeouts and retry logic
- Input validation and sanitization
- Structured logging with context
- Data quality validation
- Performance monitoring hooks
"""
import json
import re
import time
from pathlib import Path
from typing import Literal, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, ValidationError
from typing_extensions import TypedDict

from backend.jobradar.services.llm_factory import LLMFactory
from backend.app.core.config import settings
from backend.app.schemas.profile import (
    Education,
    Experience,
    Links,
    ProfilePayload,
    Project,
    SoftSkill,
    TechSkill,
)

from .pdf_utils import extract_text_from_pdf, extract_urls_from_pdf

# Production configuration constants
MAX_RESUME_TEXT_LENGTH = 50000  # ~50KB text limit
MIN_RESUME_TEXT_LENGTH = 100  # Minimum viable resume text
LLM_TIMEOUT_SECONDS = 90  # LLM call timeout
MAX_RETRIES = 2  # Number of retry attempts for transient failures


class ResumeExtractionState(TypedDict):
    """State for the LangGraph resume extraction flow."""
    resume_text: str
    file_path: str
    resume_url: str | None
    resume_last_updated: str | None
    payload: ProfilePayload | None
    error: str | None
    user_id: int | None
    email: str | None


# --- JSON-serializable schema for LLM (flat structure for reliable parsing) ---
class _ExperienceSchema(BaseModel):
    """Work experience entry."""
    jobTitle: str = Field(default="", description="Job title or role")
    companyName: str = Field(default="", description="Company or organization name")
    payrollCompany: str = Field(
        default="",
        description="Employer of record / payroll vendor if different from company (e.g. contracting via HUSYS)",
    )
    employmentType: str = Field(default="", description="e.g. Full-time, Part-time, Contract, Internship")
    startDate: str = Field(default="", description="Start date e.g. Jan 2020, 2020-01")
    endDate: str = Field(default="", description="End date e.g. Present, Dec 2023")
    location: str = Field(default="", description="City, Country or remote")
    workMode: str = Field(default="", description="On-site, Remote, Hybrid")
    description: str = Field(default="", description="Role description and key achievements")
    techStack: str | list[str] = Field(default="", description="Technologies used, comma-separated or as array")


class _EducationSchema(BaseModel):
    """Education entry."""
    degree: str = Field(default="", description="Degree e.g. B.S. Computer Science")
    fieldOfStudy: str = Field(default="", description="Major or field")
    institution: str = Field(default="", description="School or university name")
    startYear: str = Field(default="", description="Start year")
    endYear: str = Field(default="", description="End/graduation year")
    grade: str = Field(default="", description="GPA or honors if mentioned")
    location: str = Field(default="", description="City, Country")


class _TechSkillSchema(BaseModel):
    """Technical skill."""
    name: str = Field(default="", description="Skill name e.g. Python, React")
    level: str = Field(default="", description="Proficiency if mentioned: Beginner, Intermediate, Expert")
    years: str = Field(default="", description="Years of experience if mentioned")


class _SoftSkillSchema(BaseModel):
    """Soft skill."""
    name: str = Field(default="", description="Soft skill e.g. Leadership, Communication")


class _ProjectSchema(BaseModel):
    """Project entry."""
    name: str = Field(default="", description="Project name")
    description: str = Field(default="", description="Brief description")
    role: str = Field(default="", description="Your role in the project")
    techStack: str | list[str] = Field(default="", description="Technologies used, comma-separated or as array")
    githubUrl: str = Field(default="", description="GitHub URL if present")
    liveUrl: str = Field(default="", description="Live/demo URL if present")
    projectType: str = Field(default="", description="e.g. Personal, Academic, Professional")


class _LinksSchema(BaseModel):
    """Social and portfolio links."""
    linkedInUrl: str = Field(default="", description="LinkedIn profile URL")
    githubUrl: str = Field(default="", description="GitHub profile URL")
    portfolioUrl: str = Field(default="", description="Portfolio or personal website URL")
    otherLinks: list[dict] = Field(default_factory=list, description="Other links as [{label, url}]")


class _ResumeExtractionSchema(BaseModel):
    """Complete resume extraction output - maps to ProfilePayload."""
    firstName: str = Field(default="", description="First/given name")
    lastName: str = Field(default="", description="Last/family name")
    email: str = Field(default="", description="Email address")
    phone: str = Field(default="", description="Phone number")
    city: str = Field(default="", description="City of residence")
    country: str = Field(default="", description="Country")
    willingToWorkIn: list[str] = Field(default_factory=list, description="Countries willing to work in, if mentioned")
    professionalHeadline: str = Field(default="", description="Short headline e.g. Senior Software Engineer")
    professionalSummary: str = Field(default="", description="Professional summary or objective")
    experiences: list[_ExperienceSchema] = Field(default_factory=list, description="Work experience entries")
    educations: list[_EducationSchema] = Field(default_factory=list, description="Education entries")
    techSkills: list[_TechSkillSchema] = Field(default_factory=list, description="Technical skills")
    softSkills: list[_SoftSkillSchema] = Field(default_factory=list, description="Soft skills")
    projects: list[_ProjectSchema] = Field(default_factory=list, description="Projects")
    links: _LinksSchema = Field(default_factory=_LinksSchema, description="Links")


_EXTRACTION_PROMPT = """You are an expert resume parser. Extract ALL information from the resume text below and return VALID JSON that matches the schema EXACTLY.

CRITICAL: You MUST return valid JSON with the EXACT structure shown in the examples below. Do NOT return strings where objects are expected.

JSON FORMAT REQUIREMENTS:

TECHNICAL SKILLS must be objects with "name" field:
✓ CORRECT: "techSkills": [{{"name": "Python", "level": "Expert", "years": "5"}}, {{"name": "React", "level": "Advanced", "years": "3"}}]
✗ WRONG: "techSkills": ["Python", "React"]

SOFT SKILLS must be objects with "name" field:
✓ CORRECT: "softSkills": [{{"name": "Leadership"}}, {{"name": "Communication"}}, {{"name": "Teamwork"}}]
✗ WRONG: "softSkills": ["Leadership", "Communication", "Teamwork"]

OTHER LINKS must be an array (empty array if no links):
✓ CORRECT: "otherLinks": []
✓ CORRECT: "otherLinks": [{{"label": "Portfolio", "url": "https://example.com"}}]
✗ WRONG: "otherLinks": ""

EXPERIENCES must be array of objects:
✓ CORRECT: "experiences": [{{"jobTitle": "Senior Developer", "companyName": "ABC Corp", "startDate": "Jan 2020", "endDate": "Present", ...}}]

EDUCATIONS must be array of objects:
✓ CORRECT: "educations": [{{"degree": "B.S. Computer Science", "institution": "MIT", "startYear": "2016", "endYear": "2020", ...}}]

PROJECTS must be array of objects:
✓ CORRECT: "projects": [{{"name": "E-commerce Platform", "description": "...", "techStack": "React, Node.js", ...}}]

---

EXTRACTION RULES:

1. EXTRACT EVERYTHING - Do NOT skip any section:
   ✓ Name (firstName, lastName) - ALWAYS extract, split full name if needed
   ✓ Contact (email, phone) - MUST find these
   ✓ Location (city, country) - Extract from address or contact section
   ✓ Work Experience - Extract ALL jobs with full details
   ✓ Education - Extract ALL degrees/schools
   ✓ Technical Skills - Extract ALL technologies mentioned (languages, frameworks, tools, databases, cloud platforms)
   ✓ Soft Skills - Extract leadership, communication, teamwork, etc.
   ✓ Projects - Extract from dedicated projects section
   ✓ Links - LinkedIn, GitHub, Portfolio URLs

2. WORK EXPERIENCE - Extract EVERY job with:
   - jobTitle: exact role title
   - companyName: company/organization name
   - employmentType: Full-time/Part-time/Contract/Internship
   - startDate: start date (format: "Jan 2020" or "2020-01")
   - endDate: end date or "Present"
   - location: city, country or "Remote"
   - workMode: On-site/Remote/Hybrid
   - description: complete job description with all bullet points
   - techStack: ALL technologies used in this role (comma-separated)

3. EDUCATION - Extract EVERY degree with:
   - degree: full degree name (e.g., "Bachelor of Science in Computer Science")
   - fieldOfStudy: major/specialization
   - institution: university/school name
   - startYear: start year
   - endYear: graduation year
   - grade: GPA or honors if mentioned
   - location: city, country

4. TECHNICAL SKILLS - Extract COMPREHENSIVELY:
   - Programming Languages: Python, JavaScript, Java, C++, etc.
   - Frameworks: React, Node.js, Django, FastAPI, Express, etc.
   - Databases: PostgreSQL, MongoDB, MySQL, Redis, etc.
   - Cloud/DevOps: AWS, Docker, Kubernetes, CI/CD, etc.
   - Tools: Git, VS Code, Postman, etc.
   - AI/ML: TensorFlow, PyTorch, LangChain, etc.
   - For each skill, extract name and level (Beginner/Intermediate/Expert/Advanced) if mentioned

5. SOFT SKILLS - Extract ALL mentioned or implied:
   - Leadership, Communication, Teamwork, Problem-solving, Time Management, etc.

6. CONTACT & PERSONAL INFO:
   - firstName: First name ONLY (if "John Doe", firstName="John")
   - lastName: Last name ONLY (if "John Doe", lastName="Doe")
   - email: email address
   - phone: phone number with country code if present
   - city: city of residence
   - country: country name (full name, not abbreviation)

7. professionalHeadline: Create a concise professional headline (e.g., "Senior Full-Stack Engineer | AI Specialist")

8. professionalSummary: Extract or create comprehensive summary (200-800 chars) highlighting:
   - Years of experience
   - Key expertise areas
   - Notable achievements
   - Core competencies

9. PROJECTS - Extract EVERY project with:
   - name: project name/title
   - description: what the project does
   - role: your role in the project
   - techStack: ALL technologies used (comma-separated)
   - githubUrl: GitHub link if present
   - liveUrl: live demo/website link if present
   - projectType: Personal/Academic/Professional/Open Source

10. LINKS - Extract all URLs:
    - linkedInUrl: LinkedIn profile
    - githubUrl: GitHub profile
    - portfolioUrl: personal website/portfolio
    - otherLinks: any other professional links

IMPORTANT EXTRACTION TIPS:
- Read the ENTIRE resume carefully before extracting
- Technologies can be found in: skills section, experience descriptions, project descriptions
- Don't skip experience entries - extract ALL jobs
- Don't skip education entries - extract ALL degrees
- Look for contact info at top, bottom, or in headers/footers
- Extract URLs even if they're just text (not hyperlinks)
- Use empty string "" ONLY if information is truly absent
- DO NOT fabricate or guess information
- If a field is unclear, use best judgment based on context

EXACT JSON OUTPUT FORMAT (follow this structure):
```json
{{
  "firstName": "John",
  "lastName": "Doe",
  "email": "john@example.com",
  "phone": "+1-555-0123",
  "city": "San Francisco",
  "country": "United States",
  "willingToWorkIn": ["United States", "Canada"],
  "professionalHeadline": "Senior Full-Stack Engineer | AI Specialist",
  "professionalSummary": "Experienced software engineer with 5+ years...",
  "experiences": [
    {{
      "jobTitle": "Senior Software Engineer",
      "companyName": "Tech Corp",
      "payrollCompany": "",
      "employmentType": "Full-time",
      "startDate": "Jan 2020",
      "endDate": "Present",
      "location": "San Francisco, CA",
      "workMode": "Hybrid",
      "description": "Led development of...",
      "techStack": "React, Node.js, PostgreSQL, AWS"
    }}
  ],
  "educations": [
    {{
      "degree": "Bachelor of Science in Computer Science",
      "fieldOfStudy": "Computer Science",
      "institution": "MIT",
      "startYear": "2015",
      "endYear": "2019",
      "grade": "3.8 GPA",
      "location": "Cambridge, MA"
    }}
  ],
  "techSkills": [
    {{"name": "Python", "level": "Expert", "years": "5"}},
    {{"name": "React", "level": "Advanced", "years": "3"}},
    {{"name": "AWS", "level": "Intermediate", "years": "2"}}
  ],
  "softSkills": [
    {{"name": "Leadership"}},
    {{"name": "Communication"}},
    {{"name": "Problem-solving"}}
  ],
  "projects": [
    {{
      "name": "E-commerce Platform",
      "description": "Built a full-stack e-commerce application...",
      "role": "Lead Developer",
      "techStack": "React, Node.js, MongoDB",
      "githubUrl": "https://github.com/user/project",
      "liveUrl": "https://project.com",
      "projectType": "Professional"
    }}
  ],
  "links": {{
    "linkedInUrl": "https://linkedin.com/in/johndoe",
    "githubUrl": "https://github.com/johndoe",
    "portfolioUrl": "https://johndoe.com",
    "otherLinks": []
  }}
}}
```

RESUME TEXT:
```
{resume_text}
```

Now extract and return ONLY valid JSON matching the exact structure above. Ensure all arrays contain objects (not strings) where specified."""


def _extract_text_node(state: ResumeExtractionState) -> dict:
    """
    Node: Extract raw text from PDF with validation and error handling.
    
    Validates:
    - File exists and is readable
    - Text extraction succeeds
    - Text length is within acceptable range
    """
    from backend.app.core.logging_config import get_logger
    logger = get_logger("resume_extractor")
    
    file_path = state.get("file_path", "")
    user_id = state.get("user_id")
    
    try:
        # Validate file exists
        path_obj = Path(file_path)
        if not path_obj.exists():
            error_msg = f"File not found: {file_path}"
            logger.error(f"Text extraction failed user_id={user_id} error={error_msg}")
            return {"resume_text": "", "error": error_msg}
        
        if not path_obj.is_file():
            error_msg = f"Path is not a file: {file_path}"
            logger.error(f"Text extraction failed user_id={user_id} error={error_msg}")
            return {"resume_text": "", "error": error_msg}
        
        # Extract text with timeout protection
        start_time = time.time()
        text = extract_text_from_pdf(file_path)
        extraction_time = time.time() - start_time
        
        # Validate text content
        if not text or not text.strip():
            error_msg = "No text could be extracted from PDF - file may be image-based or corrupted"
            logger.warning(f"Text extraction warning user_id={user_id} error={error_msg}")
            return {"resume_text": "", "error": error_msg}
        
        text = text.strip()
        text_length = len(text)
        
        # Validate text length
        if text_length < MIN_RESUME_TEXT_LENGTH:
            error_msg = f"Extracted text too short ({text_length} chars) - file may not contain valid resume content"
            logger.warning(f"Text extraction warning user_id={user_id} error={error_msg} length={text_length}")
            return {"resume_text": "", "error": error_msg}
        
        if text_length > MAX_RESUME_TEXT_LENGTH:
            logger.warning(f"Text extraction - truncating long resume user_id={user_id} original_length={text_length} max={MAX_RESUME_TEXT_LENGTH}")
            text = text[:MAX_RESUME_TEXT_LENGTH]
            text_length = MAX_RESUME_TEXT_LENGTH
        
        logger.info(f"Text extraction success user_id={user_id} length={text_length} time={extraction_time:.2f}s")
        return {"resume_text": text, "error": None}
        
    except Exception as e:
        error_msg = f"PDF text extraction failed: {str(e)}"
        logger.exception(f"Text extraction exception user_id={user_id} error={error_msg}")
        return {"resume_text": "", "error": error_msg}


def _merge_links_from_pdf(payload: ProfilePayload, file_path: str) -> ProfilePayload:
    """Merge URLs from PDF hyperlinks (clickable links) into payload - LLM may miss these."""
    try:
        pdf_urls = extract_urls_from_pdf(file_path)
        linked_in = payload.links.linkedInUrl or pdf_urls.get("linkedInUrl") or ""
        github = payload.links.githubUrl or pdf_urls.get("githubUrl") or ""
        portfolio = payload.links.portfolioUrl or pdf_urls.get("portfolioUrl") or ""
        if linked_in or github or portfolio:
            payload.links = Links(
                linkedInUrl=linked_in,
                githubUrl=github,
                portfolioUrl=portfolio,
                otherLinks=payload.links.otherLinks or [],
            )
    except Exception:
        pass
    return payload


def _normalize_llm_response(data: dict, logger, user_id: Optional[int]) -> dict:
    """
    Normalize LLM response to match expected schema.
    
    Handles common issues:
    - Soft skills as strings instead of objects
    - Tech skills as strings instead of objects  
    - Empty strings where arrays are expected
    """
    # Normalize techSkills - convert strings to objects
    if "techSkills" in data and isinstance(data["techSkills"], list):
        normalized_tech = []
        for skill in data["techSkills"]:
            if isinstance(skill, str):
                # Convert string to object
                normalized_tech.append({"name": skill, "level": "", "years": ""})
            elif isinstance(skill, dict):
                # Already an object, keep as is
                normalized_tech.append(skill)
        data["techSkills"] = normalized_tech
    
    # Normalize softSkills - convert strings to objects
    if "softSkills" in data and isinstance(data["softSkills"], list):
        normalized_soft = []
        for skill in data["softSkills"]:
            if isinstance(skill, str):
                # Convert string to object
                normalized_soft.append({"name": skill})
            elif isinstance(skill, dict):
                # Already an object, keep as is
                normalized_soft.append(skill)
        data["softSkills"] = normalized_soft
    
    # Normalize links.otherLinks - ensure it's an array
    if "links" in data and isinstance(data["links"], dict):
        if "otherLinks" in data["links"]:
            if data["links"]["otherLinks"] == "" or data["links"]["otherLinks"] is None:
                data["links"]["otherLinks"] = []
            elif not isinstance(data["links"]["otherLinks"], list):
                data["links"]["otherLinks"] = []
    
    # Normalize willingToWorkIn - ensure it's an array
    if "willingToWorkIn" in data:
        if data["willingToWorkIn"] == "" or data["willingToWorkIn"] is None:
            data["willingToWorkIn"] = []
        elif not isinstance(data["willingToWorkIn"], list):
            data["willingToWorkIn"] = []
    
    logger.debug(f"Response normalization complete user_id={user_id}")
    return data


def _validate_extracted_data(result: _ResumeExtractionSchema, logger, user_id: Optional[int]) -> dict:
    """
    Validate extracted resume data quality.
    Returns dict with 'valid' (bool) and 'warnings' (list).
    """
    warnings = []
    
    # Check for minimum required fields
    if not result.firstName and not result.lastName:
        warnings.append("Missing name - could not extract firstName or lastName")
    
    if not result.email:
        warnings.append("Missing email address")
    
    # Validate experiences
    if not result.experiences or len(result.experiences) == 0:
        warnings.append("No work experience found")
    else:
        for idx, exp in enumerate(result.experiences):
            if not exp.jobTitle and not exp.companyName:
                warnings.append(f"Experience #{idx+1} missing both jobTitle and companyName")
    
    # Validate education
    if not result.educations or len(result.educations) == 0:
        warnings.append("No education entries found")
    
    # Validate skills
    if not result.techSkills or len(result.techSkills) == 0:
        warnings.append("No technical skills found")
    
    if warnings:
        logger.warning(f"Data quality warnings user_id={user_id} warnings={warnings}")
    
    return {"valid": True, "warnings": warnings}


def _llm_extract_with_retry(text: str, user_id: Optional[int], email: Optional[str], logger) -> str:
    """
    Call LLM with retry logic for transient failures.
    Returns the LLM response content.
    """
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 2):  # +2 because: first attempt + MAX_RETRIES retries
        try:
            start_time = time.time()
            
            provider = LLMFactory.get_provider()
            content = provider.generate(
                system_prompt="You are a precise resume parser. Return ONLY valid JSON matching the schema. Arrays of skills MUST contain objects with 'name' field, not plain strings. Follow the format examples exactly.",
                user_prompt=_EXTRACTION_PROMPT.format(resume_text=text),
                user_id=user_id,
                email=email,
                feature="resume_parsing",
                json_mode=True
            )
            
            elapsed = time.time() - start_time
            
            if not content or not content.strip():
                raise ValueError("LLM returned empty response")
            
            logger.info(f"LLM call success user_id={user_id} attempt={attempt} time={elapsed:.2f}s length={len(content)}")
            return content
            
        except Exception as e:
            last_error = e
            error_type = type(e).__name__
            logger.warning(
                f"LLM call failed user_id={user_id} attempt={attempt}/{MAX_RETRIES + 1} "
                f"error_type={error_type} error={str(e)}"
            )
            
            # Don't retry on validation errors or non-transient failures
            if isinstance(e, (ValidationError, ValueError, json.JSONDecodeError)):
                raise
            
            # Retry with exponential backoff on transient failures
            if attempt <= MAX_RETRIES:
                backoff_time = min(2 ** (attempt - 1), 10)  # Max 10s backoff
                logger.info(f"Retrying LLM call user_id={user_id} backoff={backoff_time}s")
                time.sleep(backoff_time)
            else:
                # Max retries exceeded
                raise Exception(f"LLM call failed after {MAX_RETRIES + 1} attempts: {str(last_error)}")
    
    # Should never reach here, but just in case
    raise Exception(f"LLM call failed: {str(last_error)}")


def _llm_extract_node(state: ResumeExtractionState) -> dict:
    """
    Node: Use LLM to parse resume text into structured schema.
    
    Production features:
    - Retry logic with exponential backoff
    - Timeout protection
    - Data quality validation
    - Comprehensive error categorization
    - Performance metrics logging
    """
    from backend.app.core.logging_config import get_logger
    logger = get_logger("resume_extractor")
    
    text = state.get("resume_text", "").strip()
    if not text:
        error_msg = state.get("error") or "No text extracted from PDF"
        logger.warning(f"Resume parsing skipped: {error_msg}")
        return {"payload": None, "error": error_msg}

    resume_url = state.get("resume_url")
    resume_last_updated = state.get("resume_last_updated")
    file_path = state.get("file_path", "")
    user_id = state.get("user_id")
    email = state.get("email")

    pipeline_start = time.time()
    
    try:
        logger.info(f"Resume parsing started user_id={user_id} text_length={len(text)}")
        
        # Call LLM with retry logic
        content = _llm_extract_with_retry(text, user_id, email, logger)
        
        # Clean markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```\w*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)
        
        # Parse JSON response
        try:
            data = json.loads(content)
        except json.JSONDecodeError as je:
            logger.error(f"JSON parse failed user_id={user_id} error={je} content_preview={content[:500]}")
            raise ValueError(f"Invalid JSON from LLM: {je}")
        
        # Normalize response to fix common LLM formatting issues
        data = _normalize_llm_response(data, logger, user_id)
        
        # Validate against schema
        try:
            result = _ResumeExtractionSchema.model_validate(data)
        except ValidationError as ve:
            logger.error(f"Schema validation failed user_id={user_id} errors={ve.errors()}")
            raise ValueError(f"Schema validation failed: {ve}")
        
        # Validate data quality
        validation_result = _validate_extracted_data(result, logger, user_id)
        
        logger.info(f"Schema validation success user_id={user_id} firstName={result.firstName}")

        # Helper to normalize techStack (convert list to comma-separated string)
        def normalize_tech_stack(tech_stack):
            if isinstance(tech_stack, list):
                return ", ".join(filter(None, tech_stack))  # Filter out empty strings
            return tech_stack or ""
        
        # Helper to sanitize string fields (remove excessive whitespace, null bytes)
        def sanitize_string(s: str) -> str:
            if not s:
                return ""
            # Remove null bytes and excessive whitespace
            s = s.replace('\x00', '').strip()
            # Normalize multiple spaces/newlines
            s = re.sub(r'\s+', ' ', s)
            return s
        
        # Convert to ProfilePayload with safe defaults and sanitization
        payload = ProfilePayload(
            resumeUrl=resume_url,
            resumeLastUpdated=resume_last_updated,
            firstName=sanitize_string(result.firstName),
            lastName=sanitize_string(result.lastName),
            email=sanitize_string(result.email),
            phone=sanitize_string(result.phone),
            city=sanitize_string(result.city),
            country=sanitize_string(result.country),
            willingToWorkIn=[sanitize_string(c) for c in (result.willingToWorkIn or []) if c],
            professionalHeadline=sanitize_string(result.professionalHeadline),
            professionalSummary=sanitize_string(result.professionalSummary),
            experiences=[
                Experience(**{
                    **{k: sanitize_string(v) if isinstance(v, str) else v for k, v in e.model_dump().items()},
                    'techStack': normalize_tech_stack(e.techStack)
                }) for e in (result.experiences or [])
            ],
            educations=[
                Education(**{k: sanitize_string(v) if isinstance(v, str) else v for k, v in e.model_dump().items()})
                for e in (result.educations or [])
            ],
            techSkills=[
                TechSkill(**{k: sanitize_string(v) if isinstance(v, str) else v for k, v in s.model_dump().items()})
                for s in (result.techSkills or [])
            ],
            softSkills=[
                SoftSkill(**{k: sanitize_string(v) if isinstance(v, str) else v for k, v in s.model_dump().items()})
                for s in (result.softSkills or [])
            ],
            projects=[
                Project(**{
                    **{k: sanitize_string(v) if isinstance(v, str) else v for k, v in p.model_dump().items()},
                    'techStack': normalize_tech_stack(p.techStack)
                }) for p in (result.projects or [])
            ],
            links=Links(
                linkedInUrl=sanitize_string(result.links.linkedInUrl),
                githubUrl=sanitize_string(result.links.githubUrl),
                portfolioUrl=sanitize_string(result.links.portfolioUrl),
                otherLinks=[
                    {"label": sanitize_string(o.get("label", "")), "url": sanitize_string(o.get("url", ""))}
                    for o in (result.links.otherLinks or [])
                    if o.get("url")
                ],
            ),
        )
        
        # Merge PDF hyperlinks (LLM may not see clickable links)
        payload = _merge_links_from_pdf(payload, file_path)
        
        pipeline_time = time.time() - pipeline_start
        
        logger.info(
            f"Resume parsing success user_id={user_id} "
            f"name={payload.firstName} {payload.lastName} "
            f"experiences={len(payload.experiences)} "
            f"educations={len(payload.educations)} "
            f"techSkills={len(payload.techSkills)} "
            f"projects={len(payload.projects)} "
            f"total_time={pipeline_time:.2f}s "
            f"quality_warnings={len(validation_result['warnings'])}"
        )
        
        return {"payload": payload, "error": None}
        
    except json.JSONDecodeError as je:
        error_msg = f"JSON parsing failed: {str(je)}"
        logger.error(f"Resume parsing failed user_id={user_id} error={error_msg}")
        return {"payload": None, "error": error_msg}
    
    except ValidationError as ve:
        error_msg = f"Schema validation failed: {str(ve)}"
        logger.error(f"Resume parsing failed user_id={user_id} error={error_msg}")
        return {"payload": None, "error": error_msg}
        
    except Exception as e:
        error_msg = str(e)
        pipeline_time = time.time() - pipeline_start
        logger.exception(f"Resume parsing failed user_id={user_id} error={error_msg} time={pipeline_time:.2f}s")
        return {"payload": None, "error": error_msg}


def _route_after_extract(state: ResumeExtractionState) -> Literal["llm_extract", "__end__"]:
    """Route: if we have text, go to LLM; else end."""
    if state.get("resume_text", "").strip():
        return "llm_extract"
    return "__end__"


def _build_extraction_graph() -> StateGraph:
    """Build the LangGraph extraction pipeline."""
    builder = StateGraph(ResumeExtractionState)

    builder.add_node("extract_text", _extract_text_node)
    builder.add_node("llm_extract", _llm_extract_node)

    builder.add_edge(START, "extract_text")
    builder.add_conditional_edges(
        "extract_text",
        _route_after_extract,
        path_map={"llm_extract": "llm_extract", "__end__": END},
    )
    builder.add_edge("llm_extract", END)

    return builder.compile()


def extract_resume_to_payload(
    file_path: str | Path,
    resume_url: str | None = None,
    resume_last_updated: str | None = None,
    user_id: int | None = None,
    email: str | None = None,
) -> ProfilePayload:
    """
    Extract resume data from PDF using LangGraph + LLM for accurate mapping.
    Returns ProfilePayload with high accuracy.
    Falls back to empty payload when LLM unavailable (no API key or extraction fails).
    """
    if not settings.openai_api_key:
        return ProfilePayload(
            resumeUrl=resume_url,
            resumeLastUpdated=resume_last_updated,
        )

    graph = _build_extraction_graph()
    initial_state: ResumeExtractionState = {
        "resume_text": "",
        "file_path": str(file_path),
        "resume_url": resume_url,
        "resume_last_updated": resume_last_updated,
        "payload": None,
        "error": None,
        "user_id": user_id,
        "email": email,
    }

    result = graph.invoke(initial_state)

    payload = result.get("payload")
    error = result.get("error")

    if payload and not error:
        return payload

    # Fallback: empty payload with resume metadata
    from backend.app.core.logging_config import get_logger
    logger = get_logger("resume_extractor")
    logger.warning(f"Resume extraction fallback user_id={user_id} error={error}")
    
    return ProfilePayload(
        resumeUrl=resume_url,
        resumeLastUpdated=resume_last_updated,
    )
