"""Add career_page_visits table

Revision ID: 003_career_page_visits
Revises: 002_user_resumes_jobs
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_career_page_visits"
down_revision: Union[str, None] = "003_resume_data_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "career_page_visits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("page_url", sa.String(length=2048), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("job_url", sa.String(length=2048), nullable=True),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_career_page_visits_id"), "career_page_visits", ["id"], unique=False)
    op.create_index(op.f("ix_career_page_visits_user_id"), "career_page_visits", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_career_page_visits_user_id"), table_name="career_page_visits")
    op.drop_index(op.f("ix_career_page_visits_id"), table_name="career_page_visits")
    op.drop_table("career_page_visits")
