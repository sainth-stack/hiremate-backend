"""
llm_base.py — Abstract base for all LLM providers.

Template Method pattern:
  - classify_thread, score_resume, _format_thread live HERE (shared logic)
  - Each provider only implements _complete() and chat()
"""
import json
from abc import ABC, abstractmethod
from typing import Optional, List, Dict

from backend.jobradar.services.classifier import ClassifierOutput, ScoreResponse


CLASSIFY_SYSTEM_PROMPT = """You are an AI assistant that reads job application email threads and extracts structured data.

Your task is to extract and return ONLY a JSON object with the following fields:
- is_job_related: boolean — true only if this thread is about a specific job application; false for newsletters, promotions, or generic platform emails
- company: name of the hiring company (null if not job-related)
- role: job title or role applied for (null if not job-related)
- platform: which platform the job was applied through (LinkedIn, Naukri, InstaHyre, Unstop, Wellfound, Direct, etc.) (null if not job-related)
- status: one of [applied, acknowledged, in_review, interview_scheduled, interview_completed, offer_received, rejected, withdrawn] (null if not job-related). Use "offer_received" when the email says "congratulations", "you have been selected", "pleased to offer", "welcome aboard", or any positive hiring decision. Use "interview_scheduled" for any request to schedule a call or meeting. Use "rejected" for "not moving forward", "unfortunately", "not selected".
- interview_date: ISO 8601 timestamp string if an interview is confirmed, else null
- next_action: one sentence describing what the job seeker should do next (null if not job-related)
- confidence: float between 0 and 1 representing your classification confidence
- summary: one sentence human-readable summary of the current state (null if not job-related)
- interview_process: one sentence describing the typical interview rounds for this company (e.g. '3 technical rounds followed by HR') (null if not job-related)

If is_job_related is false, set all other fields to null except confidence.
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


class LLMProvider(ABC):

    # ── Abstract interface — each provider implements these two ──────────────

    @abstractmethod
    def _complete(self, system: str, user: str) -> str:
        """
        Make a single text completion call to the underlying LLM.
        Return the raw string response.
        """

    @abstractmethod
    def chat(self, messages: List[Dict], system_instruction: str, user_id: str = None) -> str:
        """
        Handle a conversational, agentic chat with tool-calling support.
        Provider-specific because tool formats differ across SDKs.
        """

    # ── Shared logic — all providers inherit these ───────────────────────────

    def classify_thread(self, messages: List[Dict]) -> Optional[ClassifierOutput]:
        """Classify an email thread. Returns ClassifierOutput or None if not job-related."""
        thread_text = self._format_thread(messages)
        raw = self._complete(
            system=CLASSIFY_SYSTEM_PROMPT,
            user=f"Classify this email thread:\n\n{thread_text}",
        )
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            print(f"LLM: JSON decode error — raw: {raw[:200]}")
            return None

        result = ClassifierOutput(**data)
        return result if result.is_job_related else None

    def score_resume(self, resume_text: str, job_description: str) -> ScoreResponse:
        """Score a resume against a job description."""
        prompt = SCORE_RESUME_PROMPT.format(
            resume_text=resume_text,
            job_description=job_description,
        )
        raw = self._complete(system="", user=prompt)
        data = json.loads(raw.strip())
        return ScoreResponse(**data)

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
