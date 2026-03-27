"""Add legal_policies and issue_reports tables

Revision ID: 015
Revises: 014
Create Date: 2026-03-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "legal_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_legal_policies_id"), "legal_policies", ["id"], unique=False)
    op.create_index(op.f("ix_legal_policies_type"), "legal_policies", ["type"], unique=False)

    op.create_table(
        "issue_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="web"),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("screenshot_url", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_issue_reports_id"), "issue_reports", ["id"], unique=False)
    op.create_index(op.f("ix_issue_reports_user_id"), "issue_reports", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_issue_reports_user_id"), table_name="issue_reports")
    op.drop_index(op.f("ix_issue_reports_id"), table_name="issue_reports")
    op.drop_table("issue_reports")

    op.drop_index(op.f("ix_legal_policies_type"), table_name="legal_policies")
    op.drop_index(op.f("ix_legal_policies_id"), table_name="legal_policies")
    op.drop_table("legal_policies")
