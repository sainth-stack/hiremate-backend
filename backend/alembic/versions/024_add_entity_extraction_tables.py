"""Add entity extraction tables and columns

Revision ID: 024_entity_extraction
Revises: 023_skills_sections
Create Date: 2026-04-28

Adds hr_contacts, interview_events, company_profiles tables and new application columns
for structured entity extraction from emails.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "024_entity_extraction"
down_revision: Union[str, None] = "023_skills_sections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create company_profiles table
    op.create_table(
        "company_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("size_range", sa.String(), nullable=True),
        sa.Column("hq_location", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("glassdoor_rating", sa.Float(), nullable=True),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("tech_stack", sa.JSON(), nullable=True),
        sa.Column("last_enriched_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain"),
    )
    op.create_index(op.f("ix_company_profiles_id"), "company_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_company_profiles_domain"), "company_profiles", ["domain"], unique=True)

    # Add new columns to applications table
    op.add_column("applications", sa.Column("company_profile_id", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("salary_min", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("salary_max", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("salary_currency", sa.String(3), nullable=True))
    op.add_column("applications", sa.Column("salary_estimated_min", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("salary_estimated_max", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_applications_company_profile",
        "applications", "company_profiles",
        ["company_profile_id"], ["id"],
        ondelete="SET NULL"
    )

    # Create hr_contacts table
    op.create_table(
        "hr_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("source_email_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hr_contacts_id"), "hr_contacts", ["id"], unique=False)
    op.create_index(op.f("ix_hr_contacts_application_id"), "hr_contacts", ["application_id"], unique=False)

    # Create interview_events table with ENUM types
    op.create_table(
        "interview_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Enum(
            "interview", "assessment", "technical_screen", "culture_fit", "offer_call", "onboarding",
            name="eventtype"
        ), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("format", sa.Enum(
            "video", "phone", "onsite", "async_format",
            name="meetingformat"
        ), nullable=True),
        sa.Column("meeting_link", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("calendar_event_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interview_events_id"), "interview_events", ["id"], unique=False)
    op.create_index(op.f("ix_interview_events_application_id"), "interview_events", ["application_id"], unique=False)


def downgrade() -> None:
    # Drop interview_events table and its indexes
    op.drop_index(op.f("ix_interview_events_application_id"), table_name="interview_events")
    op.drop_index(op.f("ix_interview_events_id"), table_name="interview_events")
    op.drop_table("interview_events")
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS eventtype")
    op.execute("DROP TYPE IF EXISTS meetingformat")
    
    # Drop hr_contacts table and its indexes
    op.drop_index(op.f("ix_hr_contacts_application_id"), table_name="hr_contacts")
    op.drop_index(op.f("ix_hr_contacts_id"), table_name="hr_contacts")
    op.drop_table("hr_contacts")
    
    # Remove columns from applications table
    op.drop_constraint("fk_applications_company_profile", "applications", type_="foreignkey")
    op.drop_column("applications", "salary_estimated_max")
    op.drop_column("applications", "salary_estimated_min")
    op.drop_column("applications", "salary_currency")
    op.drop_column("applications", "salary_max")
    op.drop_column("applications", "salary_min")
    op.drop_column("applications", "company_profile_id")
    
    # Drop company_profiles table and its indexes
    op.drop_index(op.f("ix_company_profiles_domain"), table_name="company_profiles")
    op.drop_index(op.f("ix_company_profiles_id"), table_name="company_profiles")
    op.drop_table("company_profiles")
