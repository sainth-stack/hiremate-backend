"""Merge multiple heads (resume_versions_contexts and legal_and_issues)

Revision ID: 016
Revises: 015_resume_versions_contexts, 015
Create Date: 2026-03-27

"""
from typing import Sequence, Union

revision: str = "016"
down_revision: Union[str, Sequence[str], None] = ("015_resume_versions_contexts", "015")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
