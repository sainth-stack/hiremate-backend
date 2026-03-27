"""Placeholder for revision 014 (applied to DB but file was not committed)

Revision ID: 014
Revises: 013
Create Date: 2026-03-26

This stub exists solely to satisfy Alembic's revision chain.
The actual schema changes were already applied to the database directly.
"""
from typing import Sequence, Union

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
