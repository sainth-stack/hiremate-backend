"""
LinkedIn cold message generation API.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.dependencies import get_current_user
from backend.app.models.user import User
from backend.app.services.linkedin_cold_msg.cold_message_llm import (
    generate_cold_message,
    generate_comment,
    generate_job_answer,
)

router = APIRouter(prefix="/cold-message", tags=["cold-message"])


class ColdMessageRequest(BaseModel):
    user_intent: str = Field(..., min_length=3, max_length=1000)
    recipient_name: str | None = Field(None, max_length=120)
    company: str | None = Field(None, max_length=120)
    sender_profile_summary: str | None = Field(None, max_length=600)
    thread_context: str | None = Field(None, max_length=1200)
    tone: str = Field("professional", pattern="^(professional|casual|warm)$")


class ColdMessageResponse(BaseModel):
    message: str


@router.post("/generate", response_model=ColdMessageResponse)
async def generate(
    body: ColdMessageRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate a LinkedIn cold message draft using LLM."""
    try:
        text = await generate_cold_message(
            user_intent=body.user_intent,
            recipient_name=body.recipient_name,
            company=body.company,
            sender_summary=body.sender_profile_summary,
            thread_context=body.thread_context,
            tone=body.tone or "professional",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Generation failed")

    return ColdMessageResponse(message=text)


# ─── Comment generation ────────────────────────────────────────────────────

class GenerateCommentRequest(BaseModel):
    post_content: str | None = Field(None, max_length=1500)
    post_author: str | None = Field(None, max_length=200)
    user_intent: str | None = Field(None, max_length=500)
    sender_profile_summary: str | None = Field(None, max_length=600)
    tone: str = Field("professional", pattern="^(professional|casual|warm)$")


@router.post("/generate-comment", response_model=ColdMessageResponse)
async def generate_comment_endpoint(
    body: GenerateCommentRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate a LinkedIn post comment using LLM."""
    try:
        text = await generate_comment(
            post_content=body.post_content,
            post_author=body.post_author,
            user_intent=body.user_intent,
            sender_profile_summary=body.sender_profile_summary,
            tone=body.tone,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Generation failed")
    return ColdMessageResponse(message=text)


# ─── Job application field answer ─────────────────────────────────────────

class GenerateJobAnswerRequest(BaseModel):
    field_label: str | None = Field(None, max_length=300)
    job_title: str | None = Field(None, max_length=200)
    company: str | None = Field(None, max_length=200)
    user_intent: str | None = Field(None, max_length=500)
    sender_profile_summary: str | None = Field(None, max_length=600)
    tone: str = Field("professional", pattern="^(professional|casual|warm)$")


@router.post("/generate-job-answer", response_model=ColdMessageResponse)
async def generate_job_answer_endpoint(
    body: GenerateJobAnswerRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate a job application field answer using LLM."""
    try:
        text = await generate_job_answer(
            field_label=body.field_label,
            job_title=body.job_title,
            company=body.company,
            user_intent=body.user_intent,
            sender_profile_summary=body.sender_profile_summary,
            tone=body.tone,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Generation failed")
    return ColdMessageResponse(message=text)
