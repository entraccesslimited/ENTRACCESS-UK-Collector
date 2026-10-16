"""Geofence: the nursery's circle, and where each door check was made.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nurseries") as batch:
        batch.add_column(sa.Column("geofence_latitude", sa.Float(), nullable=True))
        batch.add_column(sa.Column("geofence_longitude", sa.Float(), nullable=True))
        batch.add_column(sa.Column("geofence_radius_m", sa.Integer(), nullable=True))
    with op.batch_alter_table("door_checks") as batch:
        for name in ("latitude", "longitude", "accuracy_m", "distance_m"):
            batch.add_column(sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("door_checks") as batch:
        for name in ("distance_m", "accuracy_m", "longitude", "latitude"):
            batch.drop_column(name)
    with op.batch_alter_table("nurseries") as batch:
        for name in ("geofence_radius_m", "geofence_longitude", "geofence_latitude"):
            batch.drop_column(name)
