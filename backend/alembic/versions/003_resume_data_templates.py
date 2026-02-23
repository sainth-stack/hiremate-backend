"""Placeholder for 003_resume_data_templates - migration file was removed but DB has this revision

Revision ID: 003_resume_data_templates
Revises: 002_user_resumes_jobs
Create Date: (legacy)

"""
from typing import Sequence, Union

from alembic import op

revision: str = "003_resume_data_templates"
down_revision: Union[str, None] = "002_user_resumes_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: schema from this revision was already applied to DB
    pass


def downgrade() -> None:
    # No-op
    pass
