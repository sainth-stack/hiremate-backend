"""Add launched_interviews tables

Revision ID: 027_launched_interviews
Revises: 026_add_interviews
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "027_launched_interviews"
down_revision: Union[str, None] = "026_add_interviews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "launched_interviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("difficulty", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("interview_created_at", sa.DateTime(), nullable=True),
        sa.Column("launched_by_user_id", sa.Integer(), nullable=True),
        sa.Column("launched_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["launched_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_launched_interviews_id"), "launched_interviews", ["id"], unique=False)
    op.create_index(
        op.f("ix_launched_interviews_interview_id"),
        "launched_interviews",
        ["interview_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_launched_interviews_launched_by_user_id"),
        "launched_interviews",
        ["launched_by_user_id"],
        unique=False,
    )

    op.create_table(
        "launched_interview_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("launched_interview_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["launched_interview_id"], ["launched_interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_launched_interview_users_id"),
        "launched_interview_users",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_launched_interview_users_launched_interview_id"),
        "launched_interview_users",
        ["launched_interview_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_launched_interview_users_user_id"),
        "launched_interview_users",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_launched_interview_users_user_id"), table_name="launched_interview_users")
    op.drop_index(
        op.f("ix_launched_interview_users_launched_interview_id"),
        table_name="launched_interview_users",
    )
    op.drop_index(op.f("ix_launched_interview_users_id"), table_name="launched_interview_users")
    op.drop_table("launched_interview_users")

    op.drop_index(
        op.f("ix_launched_interviews_launched_by_user_id"),
        table_name="launched_interviews",
    )
    op.drop_index(op.f("ix_launched_interviews_interview_id"), table_name="launched_interviews")
    op.drop_index(op.f("ix_launched_interviews_id"), table_name="launched_interviews")
    op.drop_table("launched_interviews")
