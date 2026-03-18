"""Add indexes for form field learning hot path

Revision ID: 010_form_field_learning_idx
Revises: 009_drop_company_tracker
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op


revision: str = "010_form_field_learning_idx"
down_revision: Union[str, None] = "009_drop_company_tracker"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Layer 2 hot path: (user_id, field_fp) composite
    op.create_index(
        "idx_ufa_user_fp",
        "user_field_answers",
        ["user_id", "field_fp"],
        unique=False,
        if_not_exists=True,
    )
    # Layer 3: field_fp already has index via PK on shared_field_profile_keys
    # shared_selector_performance: (field_fp, ats_platform) already exists
    # Analytics: user_submission_history by user + created
    op.create_index(
        "idx_ush_user_created",
        "user_submission_history",
        ["user_id", "submitted_at"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_ush_user_created", table_name="user_submission_history", if_exists=True)
    op.drop_index("idx_ufa_user_fp", table_name="user_field_answers", if_exists=True)
