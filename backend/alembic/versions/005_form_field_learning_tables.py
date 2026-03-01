"""Add form field learning tables - shared and per-user

Revision ID: 005_form_field_learning
Revises: 004_career_page_visits
Create Date: 2026-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_form_field_learning"
down_revision: Union[str, None] = "004_career_page_visits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shared_form_structures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("url_pattern", sa.String(500), nullable=True),
        sa.Column("ats_platform", sa.String(50), nullable=True),
        sa.Column("field_count", sa.Integer(), nullable=True),
        sa.Column("field_fps", sa.JSON(), nullable=True),
        sa.Column("has_resume_upload", sa.Boolean(), default=False),
        sa.Column("has_cover_letter", sa.Boolean(), default=False),
        sa.Column("is_multi_step", sa.Boolean(), default=False),
        sa.Column("step_count", sa.Integer(), default=1),
        sa.Column("confidence", sa.Float(), default=0.5),
        sa.Column("sample_count", sa.Integer(), default=1),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shared_form_structures_domain", "shared_form_structures", ["domain"])

    op.create_table(
        "shared_selector_performance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("field_fp", sa.String(64), nullable=False),
        sa.Column("ats_platform", sa.String(50), nullable=False),
        sa.Column("selector_type", sa.String(20), nullable=False),
        sa.Column("selector", sa.Text(), nullable=False),
        sa.Column("success_count", sa.Integer(), default=0),
        sa.Column("fail_count", sa.Integer(), default=0),
        sa.Column("last_success", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shared_selector_performance_field_fp", "shared_selector_performance", ["field_fp"])
    op.create_index("ix_shared_selector_performance_fp_ats", "shared_selector_performance", ["field_fp", "ats_platform"])

    op.create_table(
        "shared_field_profile_keys",
        sa.Column("field_fp", sa.String(64), nullable=False),
        sa.Column("ats_platform", sa.String(50), nullable=True),
        sa.Column("label_norm", sa.String(255), nullable=True),
        sa.Column("profile_key", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float(), default=0.8),
        sa.Column("vote_count", sa.Integer(), default=1),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("field_fp"),
    )

    op.create_table(
        "user_field_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("field_fp", sa.String(64), nullable=False),
        sa.Column("label_norm", sa.String(255), nullable=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("source", sa.String(20), default="llm"),
        sa.Column("confidence", sa.Float(), default=0.8),
        sa.Column("used_count", sa.Integer(), default=1),
        sa.Column("last_used", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "field_fp", name="uq_user_fp"),
    )
    op.create_index("ix_user_field_answers_user_id", "user_field_answers", ["user_id"])
    op.create_index("ix_user_field_answers_field_fp", "user_field_answers", ["field_fp"])

    op.create_table(
        "user_submission_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("ats_platform", sa.String(50), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("field_count", sa.Integer(), nullable=True),
        sa.Column("filled_count", sa.Integer(), nullable=True),
        sa.Column("unfilled_profile_keys", sa.JSON(), nullable=True),
        sa.Column("submitted_fields", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_submission_history_user_id", "user_submission_history", ["user_id"])
    op.create_index("ix_user_submission_history_user_domain", "user_submission_history", ["user_id", "domain"])


def downgrade() -> None:
    op.drop_index("ix_user_submission_history_user_domain", table_name="user_submission_history")
    op.drop_index("ix_user_submission_history_user_id", table_name="user_submission_history")
    op.drop_table("user_submission_history")

    op.drop_index("ix_user_field_answers_field_fp", table_name="user_field_answers")
    op.drop_index("ix_user_field_answers_user_id", table_name="user_field_answers")
    op.drop_table("user_field_answers")

    op.drop_table("shared_field_profile_keys")

    op.drop_index("ix_shared_selector_performance_fp_ats", table_name="shared_selector_performance")
    op.drop_index("ix_shared_selector_performance_field_fp", table_name="shared_selector_performance")
    op.drop_table("shared_selector_performance")

    op.drop_index("ix_shared_form_structures_domain", table_name="shared_form_structures")
    op.drop_table("shared_form_structures")
