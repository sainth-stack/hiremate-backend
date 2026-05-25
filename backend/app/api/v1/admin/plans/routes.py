from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.dependencies import get_admin_user, get_db
from backend.app.models.subscription_plan import SubscriptionPlan
from backend.app.models.user import User

router = APIRouter()

@router.get("/plans")
def list_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """List all subscription plans for admin."""
    plans = db.query(SubscriptionPlan).order_by(SubscriptionPlan.amount).all()
    return {"data": plans}

@router.post("/plans")
def create_plan(
    plan_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Create a new subscription plan."""
    if not plan_data.get("id"):
        # Auto-generate ID from name if not provided
        plan_data["id"] = plan_data.get("name", "").lower().replace(" ", "_")
    
    existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_data["id"]).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Plan with ID {plan_data['id']} already exists")
    
    new_plan = SubscriptionPlan(**plan_data)
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)
    return {"data": new_plan}

@router.put("/plans/{plan_id}")
def update_plan(
    plan_id: str,
    plan_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Update a subscription plan.
    If monthly_tokens is changed, all users currently on this plan have their
    token_balance immediately updated to the new quota so they don't have to
    wait for their next 30-day login reset.
    """
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    old_monthly_tokens = plan.monthly_tokens

    # If this plan is being set as featured, unset all others first
    if plan_data.get("is_featured") is True:
        db.query(SubscriptionPlan).filter(SubscriptionPlan.id != plan_id).update(
            {"is_featured": False}, synchronize_session=False
        )

    # Update fields if provided
    for key, value in plan_data.items():
        if hasattr(plan, key) and key not in ['id', 'created_at', 'updated_at']:
            setattr(plan, key, value)

    db.commit()
    db.refresh(plan)

    # If monthly_tokens changed, immediately reflect the new quota on all
    # users currently subscribed to this plan.
    new_monthly_tokens = plan.monthly_tokens
    if new_monthly_tokens != old_monthly_tokens:
        from datetime import datetime
        db.query(User).filter(User.subscription_plan == plan_id).update(
            {
                "token_balance": new_monthly_tokens,
                "last_token_reset": datetime.utcnow(),
            },
            synchronize_session=False,
        )
        db.commit()

    return {"data": plan}

@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Delete a subscription plan.
    Raises 400 if any users are currently on this plan to prevent orphaned subscriptions.
    """
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Safety check — block deletion if active subscribers exist
    subscriber_count = db.query(User).filter(User.subscription_plan == plan_id).count()
    if subscriber_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete '{plan.name}' — {subscriber_count} user(s) are currently subscribed to this plan. Deactivate it instead."
        )

    db.delete(plan)
    db.commit()
