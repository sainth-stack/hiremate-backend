"""Add user_resumes and user_jobs tables

Revision ID: 002_user_resumes_jobs
Revises: 001_initial
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_user_resumes_jobs"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_resumes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_url", sa.String(length=512), nullable=False),
        sa.Column("resume_name", sa.String(length=255), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_resumes_id"), "user_resumes", ["id"], unique=False)
    op.create_index(op.f("ix_user_resumes_user_id"), "user_resumes", ["user_id"], unique=False)

    op.create_table(
        "user_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("position_title", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("min_salary", sa.String(length=50), nullable=True),
        sa.Column("max_salary", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=20), nullable=True),
        sa.Column("period", sa.String(length=50), nullable=True),
        sa.Column("job_type", sa.String(length=50), nullable=True),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("application_status", sa.String(length=100), nullable=True),
        sa.Column("job_posting_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_jobs_id"), "user_jobs", ["id"], unique=False)
    op.create_index(op.f("ix_user_jobs_user_id"), "user_jobs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_jobs_user_id"), table_name="user_jobs")
    op.drop_index(op.f("ix_user_jobs_id"), table_name="user_jobs")
    op.drop_table("user_jobs")
    op.drop_index(op.f("ix_user_resumes_user_id"), table_name="user_resumes")
    op.drop_index(op.f("ix_user_resumes_id"), table_name="user_resumes")
    op.drop_table("user_resumes")
