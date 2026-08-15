"""Add submit fields to launched_interview_users

Revision ID: 028_launched_interview_submit
Revises: 027_launched_interviews
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "028_launched_interview_submit"
down_revision: Union[str, None] = "027_launched_interviews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "launched_interview_users",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
    )
    op.add_column(
        "launched_interview_users",
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "launched_interview_users",
        sa.Column("submission_data", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("launched_interview_users", "submission_data")
    op.drop_column("launched_interview_users", "submitted_at")
    op.drop_column("launched_interview_users", "status")
