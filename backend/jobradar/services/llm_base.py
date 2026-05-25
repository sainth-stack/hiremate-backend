"""
llm_base.py — Abstract base for all LLM providers.

Template Method pattern:
  - classify_thread, score_resume, _format_thread live HERE (shared logic)
  - Each provider only implements _complete() and chat()
"""
import json
from abc import ABC, abstractmethod
from typing import Optional, List, Dict

from backend.jobradar.services.classifier import ClassifierOutput, ScoreResponse, JDClassificationOutput


CLASSIFY_SYSTEM_PROMPT = """You are an AI assistant that reads job application email threads and extracts structured data.

Your task is to extract and return ONLY a JSON object with the following fields:
- is_job_related: boolean — true only if this thread is about a specific job application; false for newsletters, promotions, or generic platform emails
- company: name of the hiring company (null if not job-related)
- role: job title or role applied for (null if not job-related)
- platform: which platform the job was applied through (LinkedIn, Naukri, InstaHyre, Unstop, Wellfound, Direct, etc.) (null if not job-related)
- status: one of [applied, acknowledged, in_review, interview_scheduled, interview_completed, offer_received, rejected, withdrawn] (null if not job-related). Use "offer_received" when the email says "congratulations", "you have been selected", "pleased to offer", "welcome aboard", or any positive hiring decision. Use "interview_scheduled" for any request to schedule a call or meeting. Use "rejected" for "not moving forward", "unfortunately", "not selected".
- stage_type: one of [interview, assessment, technical_screen, culture_fit, offer_call, none] (null if not job-related). Use "assessment" for coding challenges, take-home assignments, or any asynchronous evaluation task. Use "interview" for scheduled interviews. Use "technical_screen" for technical/coding interviews. Use "culture_fit" for behavioral/HR rounds. Use "offer_call" for offer discussions. Use "none" if no specific stage is mentioned.
- interview_date: ISO 8601 timestamp string if an interview is confirmed, else null (DEPRECATED - use interview_events instead)
- next_action: one sentence describing what the job seeker should do next (null if not job-related)
- confidence: float between 0 and 1 representing your classification confidence
- summary: one sentence human-readable summary of the current state (null if not job-related)
- interview_process: one sentence describing the typical interview rounds for this company (e.g. '3 technical rounds followed by HR') (null if not job-related)
- interview_events: array of objects (empty array if none found, never null). Each object has:
  - event_type: one of [interview, assessment, technical_screen, culture_fit, offer_call]
  - title: descriptive title (e.g. "Technical Round 1", "Take-home coding challenge")
  - scheduled_at: ISO 8601 datetime string or null. Parse relative dates like "next Tuesday at 2pm" using the email's received date as anchor.
  - duration_minutes: integer or null
  - format: one of [video, phone, onsite, async] or null
  - meeting_link: Google Meet, Zoom, Microsoft Teams, or other meeting URL if present, else null
  - notes: any additional context (e.g. "Bring government ID", "3 interviewers")
- hr_contacts: array of objects (empty array if none found, never null). Extract ALL email addresses found, even in signatures. Each object has:
  - name: full name of the contact
  - email: email address or null
  - linkedin_url: LinkedIn profile URL or null
  - title: job title (e.g. "Technical Recruiter", "Hiring Manager") or null
- company_signals: object with company metadata (null if not found):
  - domain: company email domain (e.g. "google.com") or null
  - industry: industry/sector (e.g. "Fintech", "Healthcare") or null
  - size_range: employee count range (e.g. "51-200", "1000+") or null
  - hq_location: headquarters location (e.g. "San Francisco, CA") or null
  - tech_stack: array of technologies mentioned (e.g. ["Python", "React", "AWS"])
- salary_range: object with salary information (null if not mentioned):
  - min: minimum salary integer or null
  - max: maximum salary integer or null
  - currency: currency code (e.g. "USD", "INR") or null

IMPORTANT RULES:
1. Return empty arrays [] for interview_events and hr_contacts when none are found, NEVER return null
2. Treat assessment/coding challenge/take-home as stage_type="assessment" (still creates an interview_event)
3. Extract ALL email addresses, even from signatures
4. Parse relative dates like "next Tuesday at 2pm" by calculating from the email's received date
5. Extract meeting links from email body (Google Meet: meet.google.com, Zoom: zoom.us, Teams: teams.microsoft.com)

If is_job_related is false, set all other fields to null/empty except confidence.
Return ONLY valid JSON. No explanation, no markdown, no code fences."""


CLASSIFY_JD_SYSTEM_PROMPT = """You are an AI assistant that extracts the Company Name and Job Role from a job description.

Your task is to return ONLY a JSON object with the following fields:
- company: name of the hiring company
- role: exact job title or role
- confidence: float between 0 and 1 representing your classification confidence

Return ONLY valid JSON. No explanation, no markdown, no code fences."""


SCORE_RESUME_PROMPT = """You are a professional resume reviewer.

Resume:
{resume_text}

Job Description:
{job_description}

Analyze the match and return ONLY a JSON object with these fields:
- score: integer 0-100 representing overall fit
- verdict: one of ["Strong Match", "Moderate Match", "Weak Match"]
- matched_skills: list of skills/qualifications in both resume and JD
- missing_skills: list of important JD requirements missing from resume
- summary: a 2-3 sentence executive assessment
- suggestions: 3-5 specific, actionable bullet points to improve the resume for this JD"""


from typing import Optional, List, Dict, AsyncGenerator

class LLMProvider(ABC):
    def __init__(self):
        self.total_session_tokens: int = 0
        self.total_session_cost: float = 0.0

    def reset_usage(self):
        """Reset session usage counters."""
        self.total_session_tokens = 0
        self.total_session_cost = 0.0

    def get_usage(self) -> tuple[int, float]:
        """Return (total_tokens, total_cost) for the current session."""
        return self.total_session_tokens, self.total_session_cost

    # ── Abstract interface — each provider implements these ───────────────────

    @abstractmethod
    def _complete(
        self,
        system: str,
        user: str,
        user_id: int = None,
        email: str = None,
        feature: str = None,
        json_mode: bool = False,
        temperature: float = None,
        max_tokens: int = None,
        response_format: dict = None,
    ) -> str:
        """
        Internal: Make a single text completion call.
        """

    def generate(
        self,
        system_prompt: str,
        user_prompt: str = "",
        user_id: int = None,
        email: str = None,
        feature: str = None,
        json_mode: bool = False,
        temperature: float = None,
        max_tokens: int = None,
        response_format: dict = None,
    ) -> str:
        """
        Public API for single-turn generation.
        Note: response_format is mapped to json_mode for compatibility.
        """
        # Map response_format to json_mode for backwards compatibility
        if response_format and response_format.get("type") == "json_object":
            json_mode = True
        
        return self._complete(
            system=system_prompt,
            user=user_prompt,
            user_id=user_id,
            email=email,
            feature=feature,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

    @abstractmethod
    def generate_stream(
        self,
        system: str,
        user: str,
        user_id: int = None,
        email: str = None,
        feature: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Make a streaming completion call and yield tokens.
        Note: Token usage logging for streams is handled after the stream ends.
        """

    @abstractmethod
    def chat(self, messages: List[Dict], system_instruction: str, user_id: int = None, email: str = None, feature: str = None, mcp_client=None) -> str:
        """
        Handle a conversational, agentic chat with tool-calling support.
        Provider-specific because tool formats differ across SDKs.
        mcp_client: GmailMCPClient instance for tool dispatch; None uses direct fallback.
        """

    # ── Shared logic — all providers inherit these ───────────────────────────

    def classify_thread(self, messages: List[Dict], user_id: int = None, email: str = None) -> Optional[ClassifierOutput]:
        """Classify an email thread. Returns ClassifierOutput or None if not job-related."""
        thread_text = self._format_thread(messages)
        raw = self._complete(
            system=CLASSIFY_SYSTEM_PROMPT,
            user=f"Classify this email thread:\n\n{thread_text}",
            user_id=user_id,
            email=email,
            feature="sentinel_classification",
            json_mode=True  # Force JSON response
        )
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError as e:
            print(f"LLM: JSON decode error — {e}, raw: {raw[:500]}")
            return None

        result = ClassifierOutput(**data)
        return result if result.is_job_related else None

    def score_resume(self, resume_text: str, job_description: str, user_id: int = None, email: str = None) -> ScoreResponse:
        """Score a resume against a job description."""
        prompt = SCORE_RESUME_PROMPT.format(
            resume_text=resume_text,
            job_description=job_description,
        )
        raw = self._complete(
            system="", 
            user=prompt, 
            user_id=user_id, 
            email=email, 
            feature="resume_scoring",
            json_mode=True  # Force JSON response
        )
        try:
            data = json.loads(raw.strip())
            return ScoreResponse(**data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"LLM: Resume scoring parse error — {e}, raw: {raw[:500]}")
            raise

    def classify_jd(self, jd_text: str, user_id: int = None, email: str = None) -> Optional[JDClassificationOutput]:
        """Extract company and role from JD text."""
        if not jd_text or not jd_text.strip():
            print("LLM: Empty JD text provided")
            return None
            
        raw = self._complete(
            system=CLASSIFY_JD_SYSTEM_PROMPT,
            user=f"Extract company and role from this job description:\n\n{jd_text[:8000]}",
            user_id=user_id,
            email=email,
            feature="jd_classification",
            json_mode=True  # Force JSON response from OpenAI
        )
        try:
            print(f"LLM: Raw response: {raw[:200]}")
            data = json.loads(raw.strip())
            return JDClassificationOutput(**data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"LLM: JD parse error — {e}, raw response: {raw[:500]}")
            return None

    def _format_thread(self, messages: List[Dict]) -> str:
        """Format a list of email message dicts into a readable text block."""
        parts = []
        for msg in messages:
            parts.append(
                f"From: {msg.get('from', 'Unknown')}\n"
                f"Date: {msg.get('date', 'Unknown')}\n"
                f"Subject: {msg.get('subject', 'No Subject')}\n"
                f"Body:\n{msg.get('body', '')}"
            )
        return "\n\n---\n\n".join(parts)
