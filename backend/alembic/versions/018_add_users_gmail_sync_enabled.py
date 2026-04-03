"""Add gmail_sync_enabled to users if missing (NOT NULL, default false)

Revision ID: 018_gmail_sync
Revises: 017_add_chat_messages
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "018_gmail_sync"
down_revision: Union[str, None] = "017_add_chat_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("users")}
    if "gmail_sync_enabled" in cols:
        return
    op.add_column(
        "users",
        sa.Column(
            "gmail_sync_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("users", "gmail_sync_enabled", server_default=None)


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("users")}
    if "gmail_sync_enabled" not in cols:
        return
    op.drop_column("users", "gmail_sync_enabled")
