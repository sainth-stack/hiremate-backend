"""Add Google OAuth columns to users table

Revision ID: 012_add_google_oauth_to_users
Revises: 011_job_description_hash, 011_user_resume_per_jd
Create Date: 2026-03-25

Adds google_id, avatar_url, google_access_token, google_refresh_token, token_expiry
and makes hashed_password nullable (for OAuth-only users who have no password).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012_add_google_oauth_to_users"
down_revision: Union[str, tuple] = ("011_job_description_hash", "011_user_resume_per_jd")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(), nullable=True))
    op.add_column("users", sa.Column("google_access_token", sa.String(), nullable=True))
    op.add_column("users", sa.Column("google_refresh_token", sa.String(), nullable=True))
    op.add_column("users", sa.Column("token_expiry", sa.DateTime(), nullable=True))

    op.create_index(op.f("ix_users_google_id"), "users", ["google_id"], unique=True)

    # Make hashed_password nullable so OAuth-only users (no password) can be created
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=False)

    op.drop_index(op.f("ix_users_google_id"), table_name="users")

    op.drop_column("users", "token_expiry")
    op.drop_column("users", "google_refresh_token")
    op.drop_column("users", "google_access_token")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "google_id")
