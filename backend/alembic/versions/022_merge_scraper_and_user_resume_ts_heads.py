"""Merge heads: 021_scraper_runs and 019_user_resumes_ts

019_user_resumes_timestamps_source branched from 018_gmail_sync but had no
downstream migration; 021_scraper_runs extends fc621924edb5. This empty merge
unifies the graph so `alembic upgrade head` works.

Revision ID: 022_merge_heads_019_021
Revises: 021_scraper_runs, 019_user_resumes_ts
Create Date: 2026-04-07

"""
from typing import Sequence, Union

revision: str = "022_merge_heads_019_021"
down_revision: Union[str, Sequence[str], None] = ("021_scraper_runs", "019_user_resumes_ts")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
