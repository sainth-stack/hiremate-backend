"""
Token Pricing Configuration
"""

class TokenPricing:
    # --- Special Values ---
    UNLIMITED_PLAN_THRESHOLD = -1

    # Low balance warning threshold (warn user when balance drops below this)
    LOW_BALANCE_THRESHOLD = 5000

    # Fallback quotas when subscription_plans.monthly_tokens is unset (legacy DB rows)
    PLAN_DEFAULTS = {
        "free": 25000,
        "pro": 500000,
        "elite": -1,
    }

    @classmethod
    def resolve_monthly_tokens(cls, plan, plan_id: str) -> int:
        """Return monthly token quota from DB plan, with legacy fallbacks."""
        if plan is not None and plan.monthly_tokens is not None:
            return plan.monthly_tokens
        return cls.PLAN_DEFAULTS.get(plan_id or "free", 25000)

    @classmethod
    def is_unlimited(cls, monthly_tokens: int) -> bool:
        return monthly_tokens == cls.UNLIMITED_PLAN_THRESHOLD
