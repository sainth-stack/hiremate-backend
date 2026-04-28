"""Add user profile fields for salary estimation

Revision ID: 025_user_profile_fields
Revises: 024_entity_extraction
Create Date: 2026-04-28

Adds years_of_experience, skills, current_location, current_salary, target_salary_min
to users table for AI-powered salary estimation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "025_user_profile_fields"
down_revision: Union[str, None] = "024_entity_extraction"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add profile fields to users table
    op.add_column("users", sa.Column("years_of_experience", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("skills", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("current_location", sa.String(), nullable=True))
    op.add_column("users", sa.Column("current_salary", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("target_salary_min", sa.Integer(), nullable=True))


def downgrade() -> None:
    # Remove profile fields from users table
    op.drop_column("users", "target_salary_min")
    op.drop_column("users", "current_salary")
    op.drop_column("users", "current_location")
    op.drop_column("users", "skills")
    op.drop_column("users", "years_of_experience")
