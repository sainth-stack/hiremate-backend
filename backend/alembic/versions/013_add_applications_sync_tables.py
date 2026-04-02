"""Add applications, application_status_history, sync_status tables

Revision ID: 013_add_applications_sync_tables
Revises: 012_add_google_oauth_to_users
Create Date: 2026-03-25

Adds Gmail-synced job application tracking tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013_add_applications_sync_tables"
down_revision: Union[str, None] = "012_add_google_oauth_to_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("current_status", sa.String(), nullable=False, server_default="applied"),
        sa.Column("applied_date", sa.DateTime(), nullable=True),
        sa.Column("last_activity", sa.DateTime(), nullable=False),
        sa.Column("next_action", sa.String(), nullable=True),
        sa.Column("job_url", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("low_confidence", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("email_thread_id", sa.String(), nullable=True),
        sa.Column("interview_process", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_thread_id"),
    )
    op.create_index(op.f("ix_applications_id"), "applications", ["id"], unique=False)
    op.create_index(op.f("ix_applications_user_id"), "applications", ["user_id"], unique=False)
    op.create_index(op.f("ix_applications_email_thread_id"), "applications", ["email_thread_id"], unique=True)

    op.create_table(
        "application_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("raw_email_id", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_application_status_history_id"), "application_status_history", ["id"], unique=False)
    op.create_index(op.f("ix_application_status_history_application_id"), "application_status_history", ["application_id"], unique=False)

    op.create_table(
        "sync_status",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="idle"),
        sa.Column("total_threads", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("parsed_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("ai_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("ai_success_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_sync_status_id"), "sync_status", ["id"], unique=False)
    op.create_index(op.f("ix_sync_status_user_id"), "sync_status", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_sync_status_user_id"), table_name="sync_status")
    op.drop_index(op.f("ix_sync_status_id"), table_name="sync_status")
    op.drop_table("sync_status")

    op.drop_index(op.f("ix_application_status_history_application_id"), table_name="application_status_history")
    op.drop_index(op.f("ix_application_status_history_id"), table_name="application_status_history")
    op.drop_table("application_status_history")

    op.drop_index(op.f("ix_applications_email_thread_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_user_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_id"), table_name="applications")
    op.drop_table("applications")
