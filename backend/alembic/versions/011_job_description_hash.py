"""Stub for job_description_hash migration (already applied to DB, file was missing)

Revision ID: 011_job_description_hash
Revises: 010_form_field_learning_idx
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op


revision: str = "011_job_description_hash"
down_revision: Union[str, None] = "010_form_field_learning_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration was already applied to the DB but the file was lost.
    # No-op stub to restore the revision chain.
    pass


def downgrade() -> None:
    pass
