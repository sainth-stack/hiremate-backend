"""Add updated_at and resume_source to user_resumes if missing

Revision ID: 019_user_resumes_ts
Revises: 018_gmail_sync
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "019_user_resumes_ts"
down_revision: Union[str, None] = "018_gmail_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("user_resumes")}
    if "updated_at" not in cols:
        op.add_column(
            "user_resumes",
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
    if "resume_source" not in cols:
        op.add_column(
            "user_resumes",
            sa.Column(
                "resume_source",
                sa.String(20),
                nullable=False,
                server_default="uploaded",
            ),
        )
        op.alter_column("user_resumes", "resume_source", server_default=None)


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("user_resumes")}
    if "resume_source" in cols:
        op.drop_column("user_resumes", "resume_source")
    if "updated_at" in cols:
        op.drop_column("user_resumes", "updated_at")
