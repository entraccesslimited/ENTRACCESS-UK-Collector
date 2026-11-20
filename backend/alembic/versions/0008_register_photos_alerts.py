"""Collector photos, the arrival register, absences and non-arrival alerts.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _uuid() -> sa.Uuid:
    return sa.Uuid()


def _ts() -> sa.DateTime:
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("nurseries", sa.Column("arrival_alert_at", sa.Time(), nullable=True))
    # Every child before this attended Monday to Friday as far as the app knew.
    op.add_column(
        "children",
        sa.Column("session_days", sa.String(7), server_default="12345", nullable=False),
    )

    op.create_table(
        "collector_photos",
        sa.Column(
            "authorisation_id",
            _uuid(),
            sa.ForeignKey("authorisations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("nursery_id", _uuid(), sa.ForeignKey("nurseries.id"), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", _ts(), nullable=False),
    )
    op.create_index("ix_collector_photos_nursery_id", "collector_photos", ["nursery_id"])

    op.create_table(
        "arrivals",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("nursery_id", _uuid(), sa.ForeignKey("nurseries.id"), nullable=False),
        sa.Column(
            "child_id", _uuid(), sa.ForeignKey("children.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("arrived_at", _ts(), nullable=False),
        sa.Column("recorded_by_id", _uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recorded_offline", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=True),
        sa.Column("created_at", _ts(), nullable=False),
        sa.UniqueConstraint("child_id", "day", name="uq_arrivals_child_day"),
        sa.UniqueConstraint("client_id", name="uq_arrivals_client_id"),
    )
    op.create_index("ix_arrivals_nursery_day", "arrivals", ["nursery_id", "day"])

    op.create_table(
        "absences",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("nursery_id", _uuid(), sa.ForeignKey("nurseries.id"), nullable=False),
        sa.Column(
            "child_id", _uuid(), sa.ForeignKey("children.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "ill",
                "appointment",
                "holiday",
                "other",
                name="absence_reason",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("reported_by_id", _uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", _ts(), nullable=False),
        sa.Column("cancelled_at", _ts(), nullable=True),
    )
    op.create_index("ix_absences_nursery_day", "absences", ["nursery_id", "day"])

    op.create_table(
        "non_arrival_runs",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("nursery_id", _uuid(), sa.ForeignKey("nurseries.id"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("ran_at", _ts(), nullable=False),
        sa.Column("expected", sa.Integer(), nullable=False),
        sa.Column("missing", sa.Integer(), nullable=False),
        sa.Column("alerted", sa.Integer(), nullable=False),
        sa.Column("suppressed_reason", sa.String(300), nullable=True),
        sa.UniqueConstraint("nursery_id", "day", name="uq_non_arrival_runs_day"),
    )

    op.create_table(
        "non_arrival_alerts",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("nursery_id", _uuid(), sa.ForeignKey("nurseries.id"), nullable=False),
        sa.Column(
            "child_id", _uuid(), sa.ForeignKey("children.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("sent_at", _ts(), nullable=False),
        sa.Column("parents", sa.Integer(), nullable=False),
        sa.UniqueConstraint("child_id", "day", name="uq_non_arrival_alerts_child_day"),
    )


def downgrade() -> None:
    op.drop_table("non_arrival_alerts")
    op.drop_table("non_arrival_runs")
    op.drop_index("ix_absences_nursery_day", table_name="absences")
    op.drop_table("absences")
    op.drop_index("ix_arrivals_nursery_day", table_name="arrivals")
    op.drop_table("arrivals")
    op.drop_index("ix_collector_photos_nursery_id", table_name="collector_photos")
    op.drop_table("collector_photos")
    op.drop_column("children", "session_days")
    op.drop_column("nurseries", "arrival_alert_at")
