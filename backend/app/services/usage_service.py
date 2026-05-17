"""
UsageService - records token consumption and calculates costs.
Enforces subscription plan limits using a unified token balance.
Token usage is based entirely on real AI token consumption.
"""
from datetime import datetime
from backend.app.db.session import SessionLocal
from backend.app.models.token_usage import TokenUsage
from backend.app.models.subscription_plan import SubscriptionPlan
from backend.app.models.user import User
from backend.app.core.config import AI_PRICING
from backend.app.core.token_pricing import TokenPricing
from backend.app.core.logging_config import get_logger

logger = get_logger("services.usage")


class UsageService:
    @staticmethod
    def replenish_tokens_on_login(db, user: User):
        """
        Resets token balance to plan amount every 30 days.
        Triggered on login, register, and Google OAuth callback.
        """
        now = datetime.utcnow()
        if not user.last_token_reset or (now - user.last_token_reset).days >= 30:
            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == user.subscription_plan).first()
            if not plan:
                plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == "free").first()

            if plan:
                user.token_balance = plan.monthly_tokens
                user.last_token_reset = now
                db.add(user)
                db.commit()
                logger.info(
                    "USAGE_SERVICE: Replenished tokens for %s (%s tokens)",
                    user.email,
                    plan.monthly_tokens,
                )


def record_token_usage(
    model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    user_id: int = None,
    email: str = None,
    feature: str = None
):
    """
    Persist token usage to the database, calculate cost in USD, and deduct
    from the user's token balance.

    - Elite users (monthly_tokens == -1) are never deducted.
    - Balance is floored at 0; it will never go negative.
    - Returns (total_tokens, cost_usd).
    """
    total_tokens = prompt_tokens + completion_tokens

    # Calculate USD cost for audit log
    cost = 0.0
    pricing = AI_PRICING.get(model)
    if pricing:
        cost = (
            (prompt_tokens / 1_000_000) * pricing["prompt"] +
            (completion_tokens / 1_000_000) * pricing["completion"]
        )

    db = SessionLocal()
    try:
        # Deduct from user balance if user_id is provided
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                # Elite plan: skip deduction entirely
                plan = db.query(SubscriptionPlan).filter(
                    SubscriptionPlan.id == user.subscription_plan
                ).first()
                is_unlimited = plan and plan.monthly_tokens == TokenPricing.UNLIMITED_PLAN_THRESHOLD

                if not is_unlimited:
                    user.token_balance = max(0, user.token_balance - total_tokens)

                # Always track lifetime consumption
                user.total_tokens_consumed += total_tokens
                db.add(user)
                logger.info(
                    "TOKEN_DEDUCTION: user_id=%s email=%s deducted=%s balance=%s unlimited=%s feature=%s",
                    user_id, email, total_tokens,
                    "unlimited" if is_unlimited else user.token_balance,
                    is_unlimited, feature,
                )

        # Record audit log
        usage = TokenUsage(
            user_id=user_id,
            email=email,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            feature=feature,
        )
        db.add(usage)
        db.commit()
        return total_tokens, cost
    except Exception as e:
        logger.error("Failed to record token usage user_id=%s error=%s", user_id, str(e))
        db.rollback()
        return 0, 0.0
    finally:
        db.close()
