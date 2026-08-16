"""Add interview voice settings columns

Revision ID: 031_interview_voice
Revises: 030_interview_requests
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "031_interview_voice"
down_revision: Union[str, None] = "030_interview_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("tts_speaker", sa.String(length=64), nullable=True))
    op.add_column("interviews", sa.Column("tts_language_code", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("interviews", "tts_language_code")
    op.drop_column("interviews", "tts_speaker")
