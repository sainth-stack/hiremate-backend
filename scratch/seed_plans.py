from backend.app.db.session import SessionLocal
from backend.app.models.subscription_plan import SubscriptionPlan

def seed_tokens():
    db = SessionLocal()
    try:
        plans = [
            {
                "id": "free", 
                "monthly_tokens": 25000,
                "features": ["25,000 AI Tokens / Mo", "Standard AI Resume Studio", "Basic Job Tracking", "Email Support"]
            },
            {
                "id": "pro", 
                "monthly_tokens": 500000,
                "features": ["500,000 AI Tokens / Mo", "Advanced AI Studio", "Chrome Extension Access", "Priority Support"]
            },
            {
                "id": "elite", 
                "monthly_tokens": -1,
                "features": ["Unlimited AI Tokens", "AI Mock Interviews", "Priority AI Processing", "24/7 Priority Support"]
            },
        ]
        
        for p in plans:
            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == p["id"]).first()
            if plan:
                print(f"Updating {p['id']} tokens and features")
                plan.monthly_tokens = p["monthly_tokens"]
                plan.features = p["features"]
            else:
                print(f"Plan {p['id']} not found in DB.")
        
        db.commit()
        print("Success!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_tokens()
