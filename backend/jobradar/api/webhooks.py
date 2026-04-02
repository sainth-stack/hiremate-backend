"""
Webhook endpoint for Gmail Pub/Sub push notifications.
"""
import base64
import json

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()


class PubSubMessage(BaseModel):
    data: str
    messageId: str
    publishTime: str


class PushRequest(BaseModel):
    message: PubSubMessage
    subscription: str


@router.post("/gmail/push")
async def gmail_push_handler(request: PushRequest, background_tasks: BackgroundTasks):
    """
    Entry point for Gmail Push Notifications (Google Pub/Sub).
    Google sends a base64-encoded JSON payload: {emailAddress, historyId}.
    """
    try:
        decoded_data = base64.b64decode(request.message.data).decode("utf-8")
        data = json.loads(decoded_data)

        email_address = data.get("emailAddress")
        history_id = data.get("history_id") or data.get("historyId")

        if not email_address or not history_id:
            return {"status": "ignored", "reason": "missing_data"}

        print(f"SENTINEL: Received push for {email_address}. Triggering autonomous evaluation...")

        from backend.jobradar.services.sentinel import process_push_notification
        background_tasks.add_task(process_push_notification, email_address, str(history_id))

        return {"status": "accepted"}
    except Exception as e:
        print(f"SENTINEL: Error handling push: {e}")
        return {"status": "error", "detail": str(e)}
