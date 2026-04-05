"""Merge Gmail sync branches

Revision ID: 80ff406ef6c8
Revises: ('018_gmail_sync', '0d2384778c8b')
Create Date: 2026-04-04 13:25:50.154598

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '80ff406ef6c8'
down_revision = ('018_gmail_sync', '0d2384778c8b')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
