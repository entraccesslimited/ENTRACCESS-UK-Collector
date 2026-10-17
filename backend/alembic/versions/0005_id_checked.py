"""Record that staff checked the collector's ID before a release.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Handovers made before this was recorded read as "not recorded", which is
    # the truth, rather than as checked.
    op.add_column(
        "handovers",
        sa.Column("id_checked", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("handovers", "id_checked")
