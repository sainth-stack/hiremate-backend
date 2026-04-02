from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.user import User
from backend.jobradar.services.chat_service import ChatService
from backend.jobradar.models.chat import ChatMessage, ChatRequest, ChatResponse, ChatHistoryItem

router = APIRouter()

@router.post("", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message to the JobRadar AI assistant."""
    reply = ChatService.get_reply(db, current_user.id, req)
    return ChatResponse(reply=reply)

@router.get("", response_model=List[ChatHistoryItem])
def get_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch the recent chat history for the user."""
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [
        ChatHistoryItem(
            id=msg.id,
            role="ai" if msg.role == "model" else "user",
            content=msg.content,
            timestamp=msg.created_at
        )
        for msg in history
    ]
