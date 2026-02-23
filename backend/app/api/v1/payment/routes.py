"""
Razorpay payment gateway integration - create order and verify payment
"""
import time

import razorpay
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user
from backend.app.core.logging_config import get_logger
from backend.app.models.user import User

logger = get_logger("api.payment")
router = APIRouter()

# Plan IDs to amount in paise (1 INR = 100 paise)
PLAN_AMOUNTS = {
    "daily": 9900,   # ₹99
    "weekly": 39900,  # ₹399
    "monthly": 99900, # ₹999
}


class CreateOrderRequest(BaseModel):
    plan_id: str  # daily | weekly | monthly


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
):
    """Create a Razorpay order for the given plan. Returns order_id for frontend checkout."""
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway is not configured",
        )

    amount = PLAN_AMOUNTS.get(body.plan_id)
    if not amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan_id: {body.plan_id}. Use: daily, weekly, monthly",
        )

    try:
        client = razorpay.Client(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
        )
        receipt = f"sub_{body.plan_id}_{current_user.id}_{int(time.time())}"

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
):
    """Verify Razorpay payment signature. Call after successful payment on frontend."""
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway is not configured",
        )

    if body.plan_id not in PLAN_AMOUNTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan_id: {body.plan_id}",
        )

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

        # TODO: Store subscription in DB, grant plan access
        return {
            "success": True,
            "message": "Payment verified successfully",
            "plan_id": body.plan_id,
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
