"""
UsageService - records token consumption and calculates costs.
Enforces subscription plan limits.
"""
from datetime import datetime, timedelta
from sqlalchemy import func
from backend.app.db.session import SessionLocal
from backend.app.models.token_usage import TokenUsage
from backend.app.models.subscription_plan import SubscriptionPlan
from backend.app.models.user_resume import UserResume
from backend.app.models.user_job import UserJob
from backend.app.core.config import AI_PRICING

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
    Persist token usage to the database and calculate estimated cost.
    """
    total_tokens = prompt_tokens + completion_tokens
    
    # Calculate cost
    cost = 0.0
    pricing = AI_PRICING.get(model)
    if pricing:
        cost = (
            (prompt_tokens / 1_000_000) * pricing["prompt"] +
            (completion_tokens / 1_000_000) * pricing["completion"]
        )
    
    db = SessionLocal()
    try:
        usage = TokenUsage(
            user_id=user_id,
            email=email,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            feature=feature
        )
        db.add(usage)
        db.commit()
        return total_tokens, cost
    except Exception as e:
        print(f"USAGE_SERVICE: Failed to record usage: {e}")
        db.rollback()
        return 0, 0.0
    finally:
        db.close()

def check_feature_limit(db, user, feature_key: str):
    """
    Check if a user has exceeded their plan's quota for a specific feature.
    Returns (allowed: bool, message: str)
    """
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == user.subscription_plan).first()
    if not plan:
        # Fallback to free plan if not set
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == "free").first()
    
    if not plan:
        return True, "" # Should not happen if seeded

    limit = getattr(plan, feature_key, 0)
    
    # Unlimited check
    if limit >= 999999:
        return True, ""

    usage_count = 0
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)

    if feature_key == "resume_slots":
        usage_count = db.query(UserResume).filter(UserResume.user_id == user.id).count()
        if usage_count >= limit:
            return False, f"You have reached the limit of {limit} resumes for your plan. Upgrade to save more."

    elif feature_key == "job_tracking":
        usage_count = db.query(UserJob).filter(UserJob.user_id == user.id).count()
        if usage_count >= limit:
            return False, f"You have reached the limit of {limit} tracked jobs. Upgrade for more."

    elif feature_key == "ai_tailor_credits":
        # Count AI tailoring uses in the last 30 days
        usage_count = db.query(TokenUsage).filter(
            TokenUsage.user_id == user.id,
            TokenUsage.feature == "ai_tailor",
            TokenUsage.created_at >= month_ago
        ).count()
        if usage_count >= limit:
            return False, f"Monthly AI tailoring limit reached ({limit}/{limit}). Credits reset in a few days."

    elif feature_key == "ats_match_checks":
        # Count ATS checks in the last 30 days
        usage_count = db.query(TokenUsage).filter(
            TokenUsage.user_id == user.id,
            TokenUsage.feature == "ats_match",
            TokenUsage.created_at >= month_ago
        ).count()
        if usage_count >= limit:
            return False, f"Monthly ATS match limit reached ({limit}/{limit}). Upgrade for unlimited scans."

    return True, ""
