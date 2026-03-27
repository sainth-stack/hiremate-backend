"""Add resume_versions, tailor_contexts, user_resume_preferences tables; update user_resumes and user_jobs

Revision ID: 012_resume_versions_contexts
Revises: 011_user_resume_per_jd
Create Date: 2026-03-26

Adds:
  - resume_versions: version history per resume (trigger, snapshot, keyword score, JD)
  - tailor_contexts: DB-backed tailor context with TTL (replaces in-memory store)
  - user_resume_preferences: per-user resume editor preferences (template, fonts, colors)

Updates:
  - user_resumes: adds current_version_id, sections_order, design_config, keyword_score,
                  keyword_details, status, template_id
  - user_jobs: adds source_site column
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op


revision: str = "015_resume_versions_contexts"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── resume_versions ─────────────────────────────────────────────────────
    op.create_table(
        "resume_versions",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "resume_id",
            sa.Integer(),
            sa.ForeignKey("user_resumes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_number", sa.SmallInteger(), nullable=False),
        sa.Column("profile_snapshot", JSONB, nullable=True),
        sa.Column("design_config", JSONB, nullable=True),
        sa.Column(
            "trigger",
            sa.String(30),
            nullable=True,
            comment="initial_generate | tailor_more | manual_edit | upload | section_edit",
        ),
        sa.Column("keyword_score", sa.SmallInteger(), nullable=True),
        sa.Column("keyword_details", JSONB, nullable=True),
        sa.Column("jd_snapshot", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("resume_id", "version_number", name="uq_resume_version"),
    )
    op.create_index(
        "idx_resume_versions_resume_version",
        "resume_versions",
        ["resume_id", sa.text("version_number DESC")],
        unique=False,
    )

    # ── tailor_contexts ──────────────────────────────────────────────────────
    op.create_table(
        "tailor_contexts",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("user_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column(
            "source",
            sa.String(20),
            nullable=True,
            comment="extension | manual_paste | job_listing",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_tailor_contexts_expires_at",
        "tailor_contexts",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "idx_tailor_contexts_user_created",
        "tailor_contexts",
        ["user_id", sa.text("created_at DESC")],
        unique=False,
    )

    # ── user_resume_preferences ──────────────────────────────────────────────
    op.create_table(
        "user_resume_preferences",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "default_template_id",
            sa.String(50),
            nullable=False,
            server_default="classic-pro",
        ),
        sa.Column(
            "default_font_family",
            sa.String(100),
            nullable=False,
            server_default="Inter",
        ),
        sa.Column(
            "default_color_scheme",
            sa.String(50),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "preferred_paper_size",
            sa.String(10),
            nullable=False,
            server_default="A4",
        ),
        sa.Column(
            "default_tone",
            sa.String(20),
            nullable=False,
            server_default="professional",
        ),
        sa.Column(
            "show_keyword_score",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "auto_save_ms",
            sa.SmallInteger(),
            nullable=False,
            server_default="300",
        ),
        sa.Column("preferred_sections", JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── user_resumes: new columns ────────────────────────────────────────────
    op.add_column(
        "user_resumes",
        sa.Column("current_version_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "user_resumes",
        sa.Column("sections_order", JSONB, nullable=True),
    )
    op.add_column(
        "user_resumes",
        sa.Column("design_config", JSONB, nullable=True),
    )
    op.add_column(
        "user_resumes",
        sa.Column("keyword_score", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "user_resumes",
        sa.Column("keyword_details", JSONB, nullable=True),
    )
    op.add_column(
        "user_resumes",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="ready",
        ),
    )
    op.add_column(
        "user_resumes",
        sa.Column(
            "template_id",
            sa.String(50),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_user_resumes_status",
        "user_resumes",
        "status IN ('generating', 'ready', 'error')",
    )

    # ── user_jobs: add source_site ───────────────────────────────────────────
    op.add_column(
        "user_jobs",
        sa.Column("source_site", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_jobs", "source_site")

    op.drop_constraint("ck_user_resumes_status", "user_resumes", type_="check")
    op.drop_column("user_resumes", "template_id")
    op.drop_column("user_resumes", "status")
    op.drop_column("user_resumes", "keyword_details")
    op.drop_column("user_resumes", "keyword_score")
    op.drop_column("user_resumes", "design_config")
    op.drop_column("user_resumes", "sections_order")
    op.drop_column("user_resumes", "current_version_id")

    op.drop_table("user_resume_preferences")

    op.drop_index("idx_tailor_contexts_user_created", table_name="tailor_contexts")
    op.drop_index("idx_tailor_contexts_expires_at", table_name="tailor_contexts")
    op.drop_table("tailor_contexts")

    op.drop_index("idx_resume_versions_resume_version", table_name="resume_versions")
    op.drop_table("resume_versions")
