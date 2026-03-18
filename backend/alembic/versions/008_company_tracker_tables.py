"""Company Tracker tables: companies, user_company_tracker

Revision ID: 008_company_tracker
Revises: 007_add_mapping_analysis
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008_company_tracker"
down_revision: Union[str, None] = "007_add_mapping_analysis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("career_page_url", sa.String(length=2048), nullable=False),
        sa.Column("logo_url", sa.String(length=1024), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_id"), "companies", ["id"], unique=False)
    op.create_index(op.f("ix_companies_company_name"), "companies", ["company_name"], unique=False)
    op.create_index(op.f("ix_companies_domain"), "companies", ["domain"], unique=True)

    op.create_table(
        "user_company_tracker",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_company_tracker_id"), "user_company_tracker", ["id"], unique=False)
    op.create_index(op.f("ix_user_company_tracker_user_id"), "user_company_tracker", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_company_tracker_company_id"), "user_company_tracker", ["company_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_company_tracker_company_id"), table_name="user_company_tracker")
    op.drop_index(op.f("ix_user_company_tracker_user_id"), table_name="user_company_tracker")
    op.drop_index(op.f("ix_user_company_tracker_id"), table_name="user_company_tracker")
    op.drop_table("user_company_tracker")
    op.drop_index(op.f("ix_companies_domain"), table_name="companies")
    op.drop_index(op.f("ix_companies_company_name"), table_name="companies")
    op.drop_index(op.f("ix_companies_id"), table_name="companies")
    op.drop_table("companies")
