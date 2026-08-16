"""Add interview summary columns

Revision ID: 034_interview_summary
Revises: 033_custom_voice_clones
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "034_interview_summary"
down_revision: Union[str, None] = "033_custom_voice_clones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("launched_interviews", sa.Column("summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("launched_interviews", "summary")
    op.drop_column("interviews", "summary")
