"""Collectors added by the nursery from its registration forms.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Every collector before this was named by a parent.
    op.add_column(
        "authorisations",
        sa.Column(
            "source",
            sa.Enum("parent", "setting", name="collector_source", native_enum=False, length=32),
            server_default="parent",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("authorisations", "source")
