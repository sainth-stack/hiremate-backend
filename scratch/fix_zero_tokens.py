from backend.app.db.session import SessionLocal
from backend.app.models.user import User
from backend.app.models.subscription_plan import SubscriptionPlan
from datetime import datetime

def fix_zero_balance_users():
    db = SessionLocal()
    try:
        # Find users with 0 balance who are on the free plan
        users = db.query(User).filter(User.token_balance == 0, User.total_tokens_consumed == 0).all()
        print(f"Found {len(users)} users with 0 balance and 0 consumption.")
        
        for user in users:
            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == user.subscription_plan).first()
            if not plan:
                plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == "free").first()
            
            if plan:
                user.token_balance = plan.monthly_tokens
                # We don't reset last_token_reset here so they don't get double tokens
                print(f"Fixed {user.email}: Set balance to {plan.monthly_tokens}")
        
        db.commit()
        print("Done.")
    finally:
        db.close()

if __name__ == "__main__":
    fix_zero_balance_users()
