"""
One-time fix: Drop profiles table so it gets recreated with correct schema.
Run from project root: python backend/fix_profiles_table.py
Then restart the server.
"""
import sqlite3
from pathlib import Path

# DB is typically at project root
db_path = Path(__file__).resolve().parent.parent / "jobseeker.db"
if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.execute("DROP TABLE IF EXISTS profiles")
conn.commit()
conn.close()
print("Dropped profiles table. Restart the server to recreate it.")
