"""Enquiries from the public website.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enquiries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_name", sa.String(length=120), nullable=False),
        sa.Column("nursery_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("region", sa.String(length=60), nullable=True),
        sa.Column("children", sa.String(length=40), nullable=True),
        sa.Column("interest", sa.String(length=40), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handled_by", sa.String(length=254), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_enquiries_created", "enquiries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_enquiries_created", table_name="enquiries")
    op.drop_table("enquiries")
