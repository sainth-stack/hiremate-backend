"""Add question_count and launch voice settings

Revision ID: 032_launch_voice_settings
Revises: 031_interview_voice
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "032_launch_voice_settings"
down_revision: Union[str, None] = "031_interview_voice"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("question_count", sa.Integer(), nullable=False, server_default="15"))
    op.add_column("launched_interviews", sa.Column("voice_provider", sa.String(length=32), nullable=True))
    op.add_column("launched_interviews", sa.Column("voice_id", sa.String(length=128), nullable=True))
    op.add_column("launched_interviews", sa.Column("voice_label", sa.String(length=255), nullable=True))
    op.add_column("launched_interviews", sa.Column("tts_language_code", sa.String(length=16), nullable=True))
    op.add_column("launched_interviews", sa.Column("question_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("launched_interviews", "question_count")
    op.drop_column("launched_interviews", "tts_language_code")
    op.drop_column("launched_interviews", "voice_label")
    op.drop_column("launched_interviews", "voice_id")
    op.drop_column("launched_interviews", "voice_provider")
    op.drop_column("interviews", "question_count")
