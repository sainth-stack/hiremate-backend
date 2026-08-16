"""Add custom voice clones table

Revision ID: 033_custom_voice_clones
Revises: 032_launch_voice_settings
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "033_custom_voice_clones"
down_revision: Union[str, None] = "032_launch_voice_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_voice_clones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cartesia_voice_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cartesia_language", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("tts_language_code", sa.String(length=16), nullable=False, server_default="en-IN"),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cartesia_voice_id"),
    )
    op.create_index("ix_custom_voice_clones_cartesia_voice_id", "custom_voice_clones", ["cartesia_voice_id"])
    op.create_index("ix_custom_voice_clones_created_by_user_id", "custom_voice_clones", ["created_by_user_id"])
    op.create_index("ix_custom_voice_clones_id", "custom_voice_clones", ["id"])


def downgrade() -> None:
    op.drop_index("ix_custom_voice_clones_id", table_name="custom_voice_clones")
    op.drop_index("ix_custom_voice_clones_created_by_user_id", table_name="custom_voice_clones")
    op.drop_index("ix_custom_voice_clones_cartesia_voice_id", table_name="custom_voice_clones")
    op.drop_table("custom_voice_clones")
