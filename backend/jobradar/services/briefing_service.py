import json
import logging
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from backend.jobradar.models.briefing import CompanyBriefing
from backend.jobradar.services.classifier import BriefingData
from backend.jobradar.services.llm_factory import LLMFactory

logger = logging.getLogger(__name__)


class BriefingService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_generate_briefing(self, company: str, role: str) -> Optional[BriefingData]:
        """
        Retrieves a briefing from the cache or generates it via LLM.
        """
        company_norm = company.strip().lower()
        role_norm = role.strip().lower()

        # 1. Check Cache
        cached = (
            self.db.query(CompanyBriefing)
            .filter(
                CompanyBriefing.company_name == company_norm,
                CompanyBriefing.role_title == role_norm
            )
            .first()
        )

        if cached:
            logger.info(f"CACHE HIT: Briefing for {company}/{role}")
            return BriefingData(**cached.briefing_data)

        # 2. Generate with AI
        logger.info(f"CACHE MISS: Generating briefing for {company}/{role}")
        
        briefing_dict = self._generate_ai_briefing(company, role)
        if not briefing_dict:
            return None

        # 3. Save to Cache
        new_briefing = CompanyBriefing(
            company_name=company_norm,
            role_title=role_norm,
            briefing_data=briefing_dict
        )
        self.db.add(new_briefing)
        self.db.commit()
        self.db.refresh(new_briefing)

        return BriefingData(**briefing_dict)

    def _generate_ai_briefing(self, company: str, role: str) -> Optional[dict]:
        """
        Prompts the LLM to research the company and role.
        """
        provider = LLMFactory.get_provider()
        
        system_prompt = f"""
        You are an elite Career Coach and Corporate Recruiter specializing in technical talent.
        Your task is to provide a comprehensive PRE-INTERVIEW BRIEFING for a candidate applying to:
        Company: {company}
        Role: {role}

        You must provide a structured JSON response with the following fields:
        - company: String (Official name)
        - role: String (The target position)
        - logo: String (A single, relevant emoji)
        - industry: String (Common industries this company operates in)
        - size: String (Approximate employee count, e.g., '5,000+ employees')
        - summary: String (A 2-3 sentence overview of the company's status and what they look for in this role)
        - culture_signals: A list of 4 objects with:
            - signal: Title of the cultural trait (e.g., 'Ownership', 'Speed', 'High Bar')
            - detail: Description of how it manifests (how the candidate should prepare for it)
            - icon_type: One of ('FlashOnRoundedIcon', 'CodeRoundedIcon', 'PeopleAltRoundedIcon', 'EditNoteRoundedIcon')
            - color: A hex code representing the importance (e.g., '#2563eb', '#0ea5e9')
        - interview_rounds: A list of 4 objects representing the TYPICAL interview process for this company:
            - round: Integer (1-4)
            - name: Round title (e.g., 'Recruiter Screen', 'Technical Interview')
            - duration: String (e.g., '30 min', '60 min')
            - focus: High-level summary of what is evaluated in this round
        - topics_to_prep: A list of 5 key topics the candidate should master:
            - topic: Category or tech stack (e.g., 'System Design', 'React Performance')
            - priority: 'high', 'medium', or 'low'
            - readiness: Integer (Set a realistic baseline starting readiness like 30-50%)

        Ensure the output is pure JSON. No markdown, no triple backticks.
        """

        user_prompt = f"Generate a briefing for {company} - {role}."

        try:
            raw_response = provider.generate(system_prompt, user_prompt)
            
            # Clean response if wrapped in markdown
            if isinstance(raw_response, str):
                cleaned = raw_response.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:-3].strip()
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:-3].strip()
                return json.loads(cleaned)
            
            return raw_response
            
        except Exception as e:
            logger.error(f"Error generating briefing: {e}")
            return None
