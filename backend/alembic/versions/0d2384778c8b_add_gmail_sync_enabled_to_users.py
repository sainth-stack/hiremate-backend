"""Add gmail_sync_enabled to users

Revision ID: 0d2384778c8b
Revises: 017_add_chat_messages
Create Date: 2026-04-03 01:53:41.692741

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0d2384778c8b'
down_revision: Union[str, None] = '017_add_chat_messages'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add column as nullable first
    op.add_column('users', sa.Column('gmail_sync_enabled', sa.Boolean(), nullable=True))
    
    # Set default value for existing users
    op.execute("UPDATE users SET gmail_sync_enabled = false")
    
    # Make it non-nullable
    op.alter_column('users', 'gmail_sync_enabled', nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'gmail_sync_enabled')

