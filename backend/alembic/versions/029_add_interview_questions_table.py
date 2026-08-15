"""Add interview_questions table

Revision ID: 029_interview_questions
Revises: 028_launched_interview_submit
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "029_interview_questions"
down_revision: Union[str, None] = "028_launched_interview_submit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("template", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("expectations", sa.JSON(), nullable=True),
        sa.Column("sample_answer", sa.Text(), nullable=True),
        sa.Column("star_breakdown", sa.JSON(), nullable=True),
        sa.Column("complexity", sa.String(length=20), nullable=False),
        sa.Column("duration", sa.String(length=20), nullable=False),
        sa.Column("view_card", sa.JSON(), nullable=False),
        sa.Column("time_card", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interview_questions_id"), "interview_questions", ["id"], unique=False)
    op.create_index(
        op.f("ix_interview_questions_interview_id"),
        "interview_questions",
        ["interview_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_questions_interview_id"), table_name="interview_questions")
    op.drop_index(op.f("ix_interview_questions_id"), table_name="interview_questions")
    op.drop_table("interview_questions")
