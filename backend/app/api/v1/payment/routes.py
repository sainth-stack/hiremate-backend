"""
Razorpay payment gateway integration - create order and verify payment
"""
import time

import razorpay
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user
from backend.app.db.session import get_db
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User
from backend.app.models.subscription_plan import SubscriptionPlan
from backend.app.services.usage_service import UsageService

logger = get_logger("api.payment")
router = APIRouter()

@router.get("/plans")
def list_public_plans(db: Session = Depends(get_db)):
    """List all active subscription plans for the pricing page."""
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).all()
    # Sort by amount to show Free -> Pro -> Elite
    plans.sort(key=lambda p: p.amount)
    return {"data": plans}

class CreateOrderRequest(BaseModel):
    plan_id: str  # pro | elite


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_id: str


@router.post("/create-order", response_model=CreateOrderResponse)
def create_order(
    body: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Razorpay order for the given plan. Returns order_id for frontend checkout."""
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway is not configured",
        )

    # Fetch plan from DB
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == body.plan_id).first()
    if not plan or not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or inactive plan_id: {body.plan_id}",
        )

    amount = plan.amount
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create payment order for free plan",
        )

    try:
        client = razorpay.Client(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
        )
        receipt = f"sub_{body.plan_id}_{current_user.id}_{int(time.time())}"  # noqa: E501

        order = client.order.create(
            data={
                "amount": amount,
                "currency": "INR",
                "receipt": receipt,
            }
        )

        logger.info(
            "Razorpay order created order_id=%s plan=%s user_id=%s amount=%s",
            order["id"],
            body.plan_id,
            current_user.id,
            amount,
        )

        return CreateOrderResponse(
            order_id=order["id"],
            amount=amount,
            currency="INR",
            key_id=settings.razorpay_key_id,
        )
    except razorpay.errors.BadRequestError as e:
        logger.warning("Razorpay create order failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Razorpay create order error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment order",
        )


@router.post("/verify")
def verify_payment(
    body: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify Razorpay payment signature. Call after successful payment on frontend."""
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway is not configured",
        )

    # Fetch plan from DB
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == body.plan_id).first()
    if not plan or not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or inactive plan_id: {body.plan_id}",
        )

    # Idempotency: prevent replaying an already-processed payment
    if current_user.last_payment_id == body.razorpay_payment_id:
        return {
            "success": True,
            "message": f"Already subscribed to {body.plan_id} plan",
            "plan_id": current_user.subscription_plan,
            "expiry_date": current_user.subscription_expiry.isoformat() if current_user.subscription_expiry else None,
            "payment_id": body.razorpay_payment_id,
        }

    try:
        client = razorpay.Client(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
        )
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": body.razorpay_order_id,
                "razorpay_payment_id": body.razorpay_payment_id,
                "razorpay_signature": body.razorpay_signature,
            }
        )

        logger.info(
            "Payment verified order_id=%s payment_id=%s plan=%s user_id=%s",
            body.razorpay_order_id,
            body.razorpay_payment_id,
            body.plan_id,
            current_user.id,
        )

        # Update user subscription in DB
        expiry_date = datetime.utcnow() + timedelta(days=30)
        current_user.subscription_plan = body.plan_id
        current_user.subscription_expiry = expiry_date
        current_user.last_payment_id = body.razorpay_payment_id

        db.commit()
        db.refresh(current_user)

        # Immediately replenish token balance to the new plan's quota so the
        # user doesn't have to log out and back in to get their tokens.
        # Force replenish by clearing last_token_reset so the 30-day guard passes.
        current_user.last_token_reset = None
        db.add(current_user)
        db.commit()
        UsageService.replenish_tokens_on_login(db, current_user)

        logger.info(
            "User %s upgraded to %s until %s",
            current_user.email,
            body.plan_id,
            expiry_date
        )

        return {
            "success": True,
            "message": f"Successfully subscribed to {body.plan_id} plan",
            "plan_id": body.plan_id,
            "expiry_date": expiry_date.isoformat(),
            "payment_id": body.razorpay_payment_id,
        }
    except razorpay.errors.SignatureVerificationError as e:
        logger.warning("Razorpay signature verification failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment signature",
        )
    except Exception as e:
        logger.exception("Razorpay verify error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment verification failed",
        )
