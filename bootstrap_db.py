"""Bootstrap hiremate DB schema from SQLAlchemy models (for fresh DB when migrations fail)."""
import backend.app.models  # noqa: F401
from backend.app.db.base import Base
from backend.app.db.session import engine
from sqlalchemy import text

print("Creating tables from models...")
Base.metadata.create_all(bind=engine)

with engine.connect() as conn:
    # Ensure alembic_version exists and is stamped to head
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS alembic_version (
            version_num VARCHAR(32) NOT NULL PRIMARY KEY
        )
    """))
    conn.execute(text("DELETE FROM alembic_version"))
    conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('030_interview_requests')"))
    conn.commit()

    cols = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' ORDER BY ordinal_position"
    )).fetchall()
    print("users columns:", [c[0] for c in cols])

print("Done.")
