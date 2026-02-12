"""
Resume extraction using LangGraph + OpenAI LLM for accurate, structured mapping.
Uses pdfplumber for text extraction, then LLM for perfect schema mapping.
"""
from pathlib import Path
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

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


class ResumeExtractionState(TypedDict):
    """State for the LangGraph resume extraction flow."""
    resume_text: str
    file_path: str
    resume_url: str | None
    resume_last_updated: str | None
    payload: ProfilePayload | None
    error: str | None


# --- JSON-serializable schema for LLM (flat structure for reliable parsing) ---
class _ExperienceSchema(BaseModel):
    """Work experience entry."""
    jobTitle: str = Field(default="", description="Job title or role")
    companyName: str = Field(default="", description="Company or organization name")
    employmentType: str = Field(default="", description="e.g. Full-time, Part-time, Contract, Internship")
    startDate: str = Field(default="", description="Start date e.g. Jan 2020, 2020-01")
    endDate: str = Field(default="", description="End date e.g. Present, Dec 2023")
    location: str = Field(default="", description="City, Country or remote")
    workMode: str = Field(default="", description="On-site, Remote, Hybrid")
    description: str = Field(default="", description="Role description and key achievements")
    techStack: str = Field(default="", description="Technologies used, comma-separated")


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
    techStack: str = Field(default="", description="Technologies used")
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


_EXTRACTION_PROMPT = """You are an expert resume parser. Extract ALL information from the resume text below and map it EXACTLY to the schema.

RULES:
1. Extract every piece of information – do not omit data. Be thorough.
2. DERIVE intelligently: 
   - If "Remote" or "Work from home" appears → set workMode to "Remote"
   - If job title contains "Senior", "Lead", "Principal" → infer experienceLevel
   - If technologies are in description but not skills section → add to techSkills
   - If location is "USA" or "United States" → use proper country name
   - For dates: normalize to formats like "Jan 2020", "2020-2023", "Present"
3. Map correctly:
   - Experience: jobTitle, companyName, startDate, endDate, description, techStack (from bullets)
   - Education: degree, institution, fieldOfStudy, startYear, endYear
   - Skills: techSkills = programming, tools, frameworks; softSkills = leadership, communication, etc.
   - Links: extract LinkedIn, GitHub, portfolio URLs from text or hyperlinks
4. professionalHeadline: one short line (e.g. "Senior Full-Stack Engineer")
5. professionalSummary: full summary/objective text (up to 800 chars)
6. Use empty string "" for missing fields. Never fabricate.
7. For projects: extract from "Projects" section or notable experience bullets.

RESUME TEXT:
```
{resume_text}
```

Extract and return the complete structured data."""


def _extract_text_node(state: ResumeExtractionState) -> dict:
    """Node: Extract raw text from PDF."""
    try:
        text = extract_text_from_pdf(state["file_path"])
        return {"resume_text": text or "", "error": None}
    except Exception as e:
        return {"resume_text": "", "error": str(e)}


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


def _llm_extract_node(state: ResumeExtractionState) -> dict:
    """Node: Use LLM to parse resume text into structured schema."""
    text = state.get("resume_text", "").strip()
    if not text:
        return {"payload": None, "error": state.get("error") or "No text extracted from PDF"}

    resume_url = state.get("resume_url")
    resume_last_updated = state.get("resume_last_updated")
    file_path = state.get("file_path", "")

    try:
        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key or None,
            temperature=0,
        )
        structured_llm = llm.with_structured_output(
            _ResumeExtractionSchema, method="function_calling"
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a precise resume parser. Extract all data and map to the schema. Derive missing fields when possible."),
            ("human", _EXTRACTION_PROMPT),
        ])
        chain = prompt | structured_llm
        result: _ResumeExtractionSchema = chain.invoke({"resume_text": text})

        # Convert to ProfilePayload
        payload = ProfilePayload(
            resumeUrl=resume_url,
            resumeLastUpdated=resume_last_updated,
            firstName=result.firstName or "",
            lastName=result.lastName or "",
            email=result.email or "",
            phone=result.phone or "",
            city=result.city or "",
            country=result.country or "",
            willingToWorkIn=result.willingToWorkIn or [],
            professionalHeadline=result.professionalHeadline or "",
            professionalSummary=result.professionalSummary or "",
            experiences=[Experience(**e.model_dump()) for e in result.experiences],
            educations=[Education(**e.model_dump()) for e in result.educations],
            techSkills=[TechSkill(**s.model_dump()) for s in result.techSkills],
            softSkills=[SoftSkill(**s.model_dump()) for s in result.softSkills],
            projects=[Project(**p.model_dump()) for p in result.projects],
            links=Links(
                linkedInUrl=result.links.linkedInUrl or "",
                githubUrl=result.links.githubUrl or "",
                portfolioUrl=result.links.portfolioUrl or "",
                otherLinks=[{"label": o.get("label", ""), "url": o.get("url", "")} for o in (result.links.otherLinks or [])],
            ),
        )
        # Merge PDF hyperlinks (LLM may not see clickable links)
        payload = _merge_links_from_pdf(payload, file_path)
        return {"payload": payload, "error": None}
    except Exception as e:
        return {"payload": None, "error": str(e)}


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
    }

    result = graph.invoke(initial_state)

    payload = result.get("payload")
    error = result.get("error")

    if payload and not error:
        return payload

    # Fallback: empty payload with resume metadata
    return ProfilePayload(
        resumeUrl=resume_url,
        resumeLastUpdated=resume_last_updated,
    )
