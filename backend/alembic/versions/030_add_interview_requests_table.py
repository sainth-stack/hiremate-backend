"""Add interview_requests table

Revision ID: 030_interview_requests
Revises: 029_interview_questions
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "030_interview_requests"
down_revision: Union[str, None] = "029_interview_questions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_email", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="requested"),
        sa.Column("interview_id", sa.Integer(), nullable=True),
        sa.Column("launched_interview_user_id", sa.Integer(), nullable=True),
        sa.Column("launched_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["launched_interview_user_id"], ["launched_interview_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interview_requests_id"), "interview_requests", ["id"], unique=False)
    op.create_index(op.f("ix_interview_requests_user_id"), "interview_requests", ["user_id"], unique=False)
    op.create_index(op.f("ix_interview_requests_status"), "interview_requests", ["status"], unique=False)
    op.create_index(op.f("ix_interview_requests_interview_id"), "interview_requests", ["interview_id"], unique=False)
    op.create_index(
        op.f("ix_interview_requests_launched_interview_user_id"),
        "interview_requests",
        ["launched_interview_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_requests_launched_interview_user_id"), table_name="interview_requests")
    op.drop_index(op.f("ix_interview_requests_interview_id"), table_name="interview_requests")
    op.drop_index(op.f("ix_interview_requests_status"), table_name="interview_requests")
    op.drop_index(op.f("ix_interview_requests_user_id"), table_name="interview_requests")
    op.drop_index(op.f("ix_interview_requests_id"), table_name="interview_requests")
    op.drop_table("interview_requests")
