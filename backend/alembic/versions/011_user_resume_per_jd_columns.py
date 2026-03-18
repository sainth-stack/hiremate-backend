"""Add per-JD columns to user_resumes: resume_profile_snapshot, job_title, job_description_snippet

Revision ID: 011_user_resume_per_jd
Revises: 010_form_field_learning_idx
Create Date: 2026-03-16

Adds three new nullable columns to user_resumes so that each generated resume
can store its own profile snapshot (independent of the global profiles table)
and the job context it was generated for.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_user_resume_per_jd"
down_revision: Union[str, None] = "011_job_description_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_resumes",
        sa.Column("resume_profile_snapshot", sa.JSON(), nullable=True),
    )
    op.add_column(
        "user_resumes",
        sa.Column("job_title", sa.String(255), nullable=True),
    )
    op.add_column(
        "user_resumes",
        sa.Column("job_description_snippet", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_resumes", "job_description_snippet")
    op.drop_column("user_resumes", "job_title")
    op.drop_column("user_resumes", "resume_profile_snapshot")
