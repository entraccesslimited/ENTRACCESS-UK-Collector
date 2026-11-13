"""How the ID check was made, the never-release list, and sign-out reconciliation.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Earlier releases keep a null method: "checked, method not recorded".
    op.add_column(
        "handovers",
        sa.Column(
            "id_check_method",
            sa.Enum(
                "photo_id",
                "known_to_staff",
                "password",
                name="id_check_method",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
    )

    op.create_table(
        "restrictions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nursery_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("person_name", sa.String(length=200), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "court_order",
                "safeguarding",
                "parent_request",
                "other",
                name="restriction_reason",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["nursery_id"], ["nurseries.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ended_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restrictions_child", "restrictions", ["nursery_id", "child_id"])

    op.create_table(
        "sign_out_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nursery_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("imported_by_id", sa.Uuid(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["nursery_id"], ["nurseries.id"]),
        sa.ForeignKeyConstraint(["imported_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sign_out_imports_day", "sign_out_imports", ["nursery_id", "day"])

    op.create_table(
        "sign_outs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("nursery_id", sa.Uuid(), nullable=False),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column("child_name", sa.String(length=200), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=True),
        sa.Column("signed_out_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_by", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["import_id"], ["sign_out_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["nursery_id"], ["nurseries.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sign_outs_import", "sign_outs", ["import_id"])


def downgrade() -> None:
    op.drop_index("ix_sign_outs_import", table_name="sign_outs")
    op.drop_table("sign_outs")
    op.drop_index("ix_sign_out_imports_day", table_name="sign_out_imports")
    op.drop_table("sign_out_imports")
    op.drop_index("ix_restrictions_child", table_name="restrictions")
    op.drop_table("restrictions")
    op.drop_column("handovers", "id_check_method")
