"""Add interview session config columns to launched_interviews

Revision ID: 035_launch_session_config
Revises: 034_add_interview_summary
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035_launch_session_config"
down_revision: Union[str, None] = "034_add_interview_summary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "launched_interviews",
        sa.Column("silence_submit_seconds", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "launched_interviews",
        sa.Column("pause_duration_seconds", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "launched_interviews",
        sa.Column("max_pauses_per_interview", sa.Integer(), nullable=False, server_default="3"),
    )


def downgrade() -> None:
    op.drop_column("launched_interviews", "max_pauses_per_interview")
    op.drop_column("launched_interviews", "pause_duration_seconds")
    op.drop_column("launched_interviews", "silence_submit_seconds")
