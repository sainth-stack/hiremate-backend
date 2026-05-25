import json
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.jobradar.services.llm_factory import LLMFactory
from backend.jobradar.models.application import Application
from backend.jobradar.models.chat import ChatMessage, ChatRequest

class ChatService:
    @staticmethod
    def get_reply(db: Session, user_id: int, email: str, req: ChatRequest) -> str:
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
            "You have access to the user's current job application data AND live Gmail search tools. "
            "Your ONLY purpose is to help the user with their job hunt, career advice, and application tracking.\n\n"
            "STRICT GUARDRAILS:\n"
            "- DO NOT answer questions about general programming, cooking, history, or anything unrelated to job searching.\n"
            "- If the user asks an off-topic question, politely refuse and redirect them to ask about their applications or career.\n"
            "- Never provide code snippets unless they are related to job application automation or data analysis.\n\n"
            "MANDATORY TOOL USAGE — NEVER SKIP THIS:\n"
            "- NEVER say 'I cannot search', 'I am unable to search', or 'I don't have access to your emails'. You DO have access via the tools.\n"
            "- ALWAYS call a tool first before responding to any question about emails, companies, recruiters, or application status.\n"
            "- If the user mentions any name, company, recruiter, or job reference — immediately call 'search_threads' with that as the query.\n"
            "- Do NOT make assumptions about whether something is in the inbox. Always search first, answer after.\n\n"
            "COGNITIVE PROTOCOL:\n"
            "1. If a company/name is IN the application list below AND has an email_thread_id → call 'get_thread' with that thread_id.\n"
            "2. If NOT in the list, or no thread_id → call 'search_threads' with the company/name/keyword as query.\n"
            "3. After 'search_threads' returns results → extract the thread_id from results and call 'get_thread' to read the full email.\n"
            "4. Only after reading the actual email content should you answer the user's question.\n\n"
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

        # 4. Build MCP client (connects to remote MCP server if configured, else uses direct API)
        from backend.jobradar.services.mcp_gmail_client import GmailMCPClient
        mcp_client = GmailMCPClient(user_id, db).connect()

        # 5. Query the LLM
        reply = llm.chat(
            messages,
            system_instruction,
            user_id=user_id,
            email=email,
            feature="chat_interaction",
            
            mcp_client=mcp_client,
        )
        
        # 5. Save and return reply
        db.add(ChatMessage(
            user_id=user_id,
            role="model",
            content=reply
        ))
        db.commit()
        
        return reply
