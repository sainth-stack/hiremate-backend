
from backend.app.db.session import SessionLocal
from backend.app.models.token_usage import TokenUsage
from sqlalchemy import desc

def check_recent_usage():
    db = SessionLocal()
    try:
        recent = db.query(TokenUsage).order_by(desc(TokenUsage.created_at)).limit(10).all()
        print(f"{'ID':<5} | {'User':<5} | {'Email':<25} | {'Model':<20} | {'Tokens':<10} | {'Cost':<10} | {'Feature'}")
        print("-" * 100)
        for r in recent:
            print(f"{r.id:<5} | {str(r.user_id):<5} | {str(r.email):<25} | {r.model:<20} | {r.total_tokens:<10} | {r.cost:<10.6f} | {r.feature}")
    finally:
        db.close()

if __name__ == "__main__":
    check_recent_usage()
