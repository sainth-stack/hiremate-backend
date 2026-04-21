"""
UsageService - records token consumption and calculates costs.
"""
from backend.app.db.session import SessionLocal
from backend.app.models.token_usage import TokenUsage
from backend.app.core.config import settings, AI_PRICING

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
