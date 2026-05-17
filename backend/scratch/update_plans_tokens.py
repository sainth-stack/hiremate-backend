from backend.app.db.session import SessionLocal
from backend.app.models.subscription_plan import SubscriptionPlan

def update_plans():
    db = SessionLocal()
    try:
        plans_data = {
            "free": 25000,
            "pro": 500000,
            "elite": -1
        }
        for plan_id, tokens in plans_data.items():
            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
            if plan:
                plan.monthly_tokens = tokens
                print(f"Updated {plan_id} with {tokens} tokens")
            else:
                print(f"Plan {plan_id} not found")
        db.commit()
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_plans()
