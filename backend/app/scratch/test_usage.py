"""
Test Token Usage Recording
"""
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from backend.app.services.usage_service import record_token_usage
from backend.app.db.session import SessionLocal
from backend.app.models.token_usage import TokenUsage

def test_usage_recording():
    print("TEST: Starting token usage recording test...")
    
    # Use a dummy model and count
    model_name = "gpt-4o-mini"
    prompt_tokens = 1000
    completion_tokens = 500
    email = "test@example.com"
    feature = "unit_test"
    
    # 1. Record usage
    record_token_usage(
        model=model_name,
        provider="openai",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        user_id=None,
        email=email,
        feature=feature
    )
    
    # 2. Verify in DB
    db = SessionLocal()
    try:
        usage = db.query(TokenUsage).filter(TokenUsage.email == email, TokenUsage.feature == feature).order_by(TokenUsage.id.desc()).first()
        if usage:
            print(f"PASS: Recorded usage found. ID: {usage.id}")
            print(f"      Model: {usage.model}, Provider: {usage.provider}")
            print(f"      Tokens: P={usage.prompt_tokens}, C={usage.completion_tokens}, T={usage.total_tokens}")
            print(f"      Cost: ${usage.cost:.6f}")
            
            # Verify cost calculation
            # for gpt-4o-mini: prompt=0.15/1M, completion=0.60/1M
            # (1000/1M)*0.15 + (500/1M)*0.60 = 0.00015 + 0.00030 = 0.00045
            expected_cost = 0.00045
            if abs(usage.cost - expected_cost) < 1e-9:
                 print("PASS: Cost calculation is accurate.")
            else:
                 print(f"FAIL: Cost mismatch. Expected: {expected_cost}, Got: {usage.cost}")
        else:
            print("FAIL: No usage record found in DB.")
    finally:
        db.close()

if __name__ == "__main__":
    test_usage_recording()
