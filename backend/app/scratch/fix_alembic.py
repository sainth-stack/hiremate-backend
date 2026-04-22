import sys
import os
from sqlalchemy import text

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from backend.app.db.session import SessionLocal

def fix_alembic():
    db = SessionLocal()
    try:
        # Update version to the last known head
        print("FIX: Updating alembic_version to 022_merge_heads_019_021...")
        db.execute(text("UPDATE alembic_version SET version_num = '022_merge_heads_019_021'"))
        db.commit()
        print("FIX: Done.")
    except Exception as e:
        print(f"FIX: Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_alembic()
