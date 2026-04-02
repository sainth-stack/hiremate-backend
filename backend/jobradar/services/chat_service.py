import json
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.jobradar.services.llm_factory import LLMFactory
from backend.jobradar.models.application import Application
from backend.jobradar.models.chat import ChatMessage, ChatRequest

class ChatService:
    @staticmethod
    def get_reply(db: Session, user_id: int, req: ChatRequest) -> str:
        # 1. Save user's incoming message
        db.add(ChatMessage(
            user_id=user_id,
            role="user",
            content=req.message
        ))
        db.commit()
        
        # 2. Fetch status context so the AI knows their specific jobs
        apps = db.query(Application).filter(Application.user_id == user_id).all()
        
        app_list = []
        for app in apps:
            app_list.append({
                "company": app.company,
                "role": app.role,
                "platform": app.platform,
                "current_status": app.current_status,
                "applied_date": app.applied_date.isoformat() if app.applied_date else None,
                "last_activity": app.last_activity.isoformat() if app.last_activity else None,
                "next_action": app.next_action,
                "email_thread_id": app.email_thread_id
            })
            
        context = json.dumps(app_list, indent=2)
        
        today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
        system_instruction = (
            f"Today's date is {today}. Always use this date when the user says 'today', 'yesterday', 'this week', or any relative time reference.\n\n"
            "You are JobRadar, an intelligent job search assistant. "
            "You have access to the user's current job application data below. "
            "Your ONLY purpose is to help the user with their job hunt, career advice, and application tracking. \n\n"
            "STRICT GUARDRAILS:\n"
            "- DO NOT answer questions about general programming, cooking, history, or anything unrelated to job searching.\n"
            "- If the user asks an off-topic question, politely refuse and redirect them to ask about their applications or career.\n"
            "- Never provide code snippets unless they are related to job application automation or data analysis (e.g., writing a follow-up email is okay, but 'HelloWorld in Python' is NOT).\n\n"
            "COGNITIVE PROTOCOL:\n"
            "1. If a company is IN the list below, use 'fetch_raw_email' for deep dives.\n"
            "2. If a company is NOT in the list (e.g., Glassdoor, Naukri, or random job emails), you MUST use 'search_gmail_inbox' to find relevant threads first.\n"
            "3. Once you have a Thread ID from the search results, you can then use 'fetch_raw_email' to read its text.\n"
            "Never tell the user you lack access—you have the tools to search and fetch anything in their live inbox.\n\n"
            f"Application Data:\n{context}"
        )
        
        llm = LLMFactory.get_provider()
        
        # 3. Fetch chat history (limit 15)
        history_msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(15)
            .all()
        )
        history_msgs.reverse()
        
        messages = [{"role": msg.role, "content": msg.content} for msg in history_msgs]
        
        # 4. Query the LLM
        reply = llm.chat(messages, system_instruction, user_id=user_id)
        
        # 5. Save and return reply
        db.add(ChatMessage(
            user_id=user_id,
            role="model",
            content=reply
        ))
        db.commit()
        
        return reply
