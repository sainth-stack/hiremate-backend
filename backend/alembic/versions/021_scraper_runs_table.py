"""Add scraper_runs table for ingest analytics

Revision ID: 021_scraper_runs
Revises: 020_jobs_corpus
Create Date: 2026-04-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "021_scraper_runs"
down_revision: Union[str, None] = "020_jobs_corpus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_json = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "scraper_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("inserted", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("filtered_out", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("total_jobs_seen", sa.Integer(), nullable=False),
        sa.Column("total_inserted", sa.Integer(), nullable=False),
        sa.Column("total_filtered", sa.Integer(), nullable=False),
        sa.Column("detail_json", _json, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scraper_runs_id"), "scraper_runs", ["id"], unique=False)
    op.create_index(op.f("ix_scraper_runs_source"), "scraper_runs", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scraper_runs_source"), table_name="scraper_runs")
    op.drop_index(op.f("ix_scraper_runs_id"), table_name="scraper_runs")
    op.drop_table("scraper_runs")
