"""Add mapping_analysis to user_submission_history

Revision ID: 007_add_mapping_analysis
Revises: 006_add_user_is_admin
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007_add_mapping_analysis"
down_revision: Union[str, None] = "006_add_user_is_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_submission_history", sa.Column("mapping_analysis", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_submission_history", "mapping_analysis")
