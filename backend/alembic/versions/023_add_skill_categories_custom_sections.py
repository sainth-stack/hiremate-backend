"""Add skill_categories and custom_sections to profiles

Revision ID: 023_skills_sections
Revises: 372e2c7d8198
Create Date: 2026-04-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "023_skills_sections"
down_revision: Union[str, None] = "372e2c7d8198"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("profiles")}
    
    # Add skill_categories column if it doesn't exist
    if "skill_categories" not in cols:
        op.add_column(
            "profiles",
            sa.Column("skill_categories", sa.JSON(), nullable=True),
        )
        # Set default empty list for existing rows
        conn.execute(sa.text("UPDATE profiles SET skill_categories = '[]' WHERE skill_categories IS NULL"))
    
    # Add custom_sections column if it doesn't exist
    if "custom_sections" not in cols:
        op.add_column(
            "profiles",
            sa.Column("custom_sections", sa.JSON(), nullable=True),
        )
        # Set default empty list for existing rows
        conn.execute(sa.text("UPDATE profiles SET custom_sections = '[]' WHERE custom_sections IS NULL"))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("profiles")}
    
    if "custom_sections" in cols:
        op.drop_column("profiles", "custom_sections")
    
    if "skill_categories" in cols:
        op.drop_column("profiles", "skill_categories")
