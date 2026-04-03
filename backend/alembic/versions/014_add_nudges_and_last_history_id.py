"""Add nudges table and last_history_id to users

Revision ID: 014_add_nudges_and_last_history_id
Revises: 013_add_applications_sync_tables
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013_add_applications_sync_tables"
branch_labels = None
depends_on = None


def upgrade():
    # Add last_history_id to users for incremental Gmail sync
    op.add_column("users", sa.Column("last_history_id", sa.String(), nullable=True))

    # Create nudges table
    op.create_table(
        "nudges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("nudge_type", sa.String(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_nudges_user_id", "nudges", ["user_id"])


def downgrade():
    op.drop_index("ix_nudges_user_id", table_name="nudges")
    op.drop_table("nudges")
    op.drop_column("users", "last_history_id")
