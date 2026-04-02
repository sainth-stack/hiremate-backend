import logging
from sqlalchemy.orm import Session
from backend.jobradar.services.providers.gemini import GeminiProvider
from backend.jobradar.models.nudge import Nudge

logger = logging.getLogger("uvicorn.error")

def generate_nudge(db: Session, user_id: int, app_id: int, company: str, role: str, new_status: str, is_new: bool = False):
    """
    Generates a contextual nudge via Gemini based on the application's current state.
    Inserts the generated 1-sentence message directly into the nudges table.
    """
    try:
        if is_new:
            prompt = f"The user just applied for a {role} role at {company}. The status is '{new_status}'. Write exactly one short, encouraging sentence telling them what to expect next or what they should do to stand out."
        else:
            prompt = f"The user's application for the {role} role at {company} just updated its status to '{new_status}'. Write exactly one short, encouraging sentence telling them what their very next step or mindset should be."

        messages = [{"role": "user", "content": prompt}]
        sys_prompt = "You are an AI career coach inside a dashboard. Be concise, friendly, and highly actionable. No greetings, just give the one sentence advice."
        
        provider = GeminiProvider()
        response_text = provider.chat(messages, sys_prompt)

        if response_text:
            db.add(Nudge(
                user_id=user_id,
                application_id=app_id,
                message=response_text.strip(),
                nudge_type=new_status,
                is_read=False
            ))
            db.commit()
            logger.info(f"✨ Generated Nudge for app {app_id}: {response_text.strip()[:60]}...")

    except Exception as e:
        logger.error(f"❌ Failed to generate AI nudge for {company}: {e}")
