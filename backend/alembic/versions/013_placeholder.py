"""Placeholder for revision 013 (applied to DB but file was not committed)

Revision ID: 013
Revises: 011_user_resume_per_jd
Create Date: 2026-03-26

This stub exists solely to satisfy Alembic's revision chain.
The actual schema changes (applications, nudges, sync_status tables etc.)
were already applied to the database directly.
"""
from typing import Sequence, Union

revision: str = "013"
down_revision: Union[str, None] = "011_user_resume_per_jd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
