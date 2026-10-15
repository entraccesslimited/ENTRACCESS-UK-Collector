"""The data model.

Six tables carry the product: nurseries, the people who use them (admins,
staff and parents), children, who is linked to whom, the authorisations
parents give, and the record of what happened at the door. Every row outside
`nurseries` carries a `nursery_id`, and every query in the app filters on it.

Two of them are append-only by design. A door check and a handover are never
updated or deleted: the cases where this record is read are disputes about a
child's safety, and a record that can be edited into a different answer is
worth nothing at that moment.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """A timestamp that always comes back timezone-aware, in UTC.

    Postgres does this on its own; SQLite, used in tests and small installs,
    hands back naive values, and a naive time reaches the browser without a
    zone and is read as local time — an hour out for half the year in the UK.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:  # noqa: ARG002
        if value is not None and value.tzinfo is None:
            raise ValueError("Store timezone-aware datetimes only.")
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(
        self,
        value: datetime | None,
        dialect: Dialect,  # noqa: ARG002
    ) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Role(enum.StrEnum):
    ADMIN = "admin"
    STAFF = "staff"
    PARENT = "parent"


class CollectorKind(enum.StrEnum):
    # Collects on any day inside the validity window, with a code that changes
    # every day.
    REGULAR = "regular"
    # Collects once, inside a short window. The pass stops working the moment
    # the child is released to them.
    ONE_OFF = "one_off"


class CheckMethod(enum.StrEnum):
    PASS = "pass"
    CODE = "code"


class CheckResult(enum.StrEnum):
    VALID = "valid"
    UNREADABLE = "unreadable"
    WRONG_NURSERY = "wrong_nursery"
    UNKNOWN = "unknown"
    REVOKED = "revoked"
    REISSUED = "reissued"
    NOT_YET_VALID = "not_yet_valid"
    EXPIRED = "expired"
    ALREADY_USED = "already_used"
    WRONG_CODE = "wrong_code"
    LOCKED = "locked"


class HandoverOutcome(enum.StrEnum):
    RELEASED = "released"
    REFUSED = "refused"


def _enum(kind: type[enum.Enum], name: str) -> Enum:
    return Enum(
        kind,
        name=name,
        native_enum=False,
        values_callable=lambda members: [m.value for m in members],
        length=32,
    )


class Nursery(Base):
    __tablename__ = "nurseries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/London")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nursery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nurseries.id"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    role: Mapped[Role] = mapped_column(_enum(Role, "role"))
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    nursery: Mapped[Nursery] = relationship()


class Child(Base):
    __tablename__ = "children"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nursery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nurseries.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    room: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ParentLink(Base):
    """A parent or carer with parental responsibility for a child."""

    __tablename__ = "parent_links"
    __table_args__ = (UniqueConstraint("parent_id", "child_id", name="uq_parent_child"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nursery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nurseries.id"), index=True)
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    child_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"))
    relationship_label: Mapped[str] = mapped_column(String(60), default="Parent")

    parent: Mapped[User] = relationship()
    child: Mapped[Child] = relationship()


class Authorisation(Base):
    """A parent naming someone who may collect their child.

    Nothing secret is stored. The collector's pass and their daily code are
    derived from this row's id and version under the nursery's key, so a
    backup holds no list of ways to take children home. Moving the version
    ("reissue") stops the old pass and code at once; setting `revoked_at`
    stops everything for good.
    """

    __tablename__ = "authorisations"
    __table_args__ = (Index("ix_authorisations_child", "nursery_id", "child_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nursery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nurseries.id"), index=True)
    child_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"))
    authorised_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    collector_name: Mapped[str] = mapped_column(String(200))
    collector_relationship: Mapped[str] = mapped_column(String(60))
    collector_phone: Mapped[str] = mapped_column(String(40))
    # A word the collector is asked at the door, on top of the pass. Optional;
    # many settings already use a password system and keep it.
    note_for_staff: Mapped[str | None] = mapped_column(String(300))

    kind: Mapped[CollectorKind] = mapped_column(_enum(CollectorKind, "collector_kind"))
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime())
    valid_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    version: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # Set when a one-off collector has collected: the pass cannot be used twice.
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    child: Mapped[Child] = relationship()
    authorised_by: Mapped[User] = relationship(foreign_keys=[authorised_by_id])


class DoorCheck(Base):
    """Every attempt to verify a collector, whatever the answer. Append-only."""

    __tablename__ = "door_checks"
    __table_args__ = (Index("ix_door_checks_nursery_time", "nursery_id", "checked_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nursery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nurseries.id"))
    checked_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    method: Mapped[CheckMethod] = mapped_column(_enum(CheckMethod, "check_method"))
    result: Mapped[CheckResult] = mapped_column(_enum(CheckResult, "check_result"))
    child_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("children.id"))
    authorisation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("authorisations.id"))
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    checked_by: Mapped[User] = relationship()
    child: Mapped[Child | None] = relationship()
    authorisation: Mapped[Authorisation | None] = relationship()


class Handover(Base):
    """What staff decided after a valid check. Append-only.

    The names are copied in rather than joined, so the record reads the same
    after a collector is revoked or a member of staff leaves.
    """

    __tablename__ = "handovers"
    __table_args__ = (Index("ix_handovers_nursery_time", "nursery_id", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nursery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nurseries.id"))
    door_check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("door_checks.id"), unique=True)
    child_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("children.id"))
    authorisation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authorisations.id"))
    outcome: Mapped[HandoverOutcome] = mapped_column(_enum(HandoverOutcome, "handover_outcome"))
    refusal_reason: Mapped[str | None] = mapped_column(Text)

    child_name: Mapped[str] = mapped_column(String(200))
    collector_name: Mapped[str] = mapped_column(String(200))
    collector_relationship: Mapped[str] = mapped_column(String(60))
    authorised_by_name: Mapped[str] = mapped_column(String(200))
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    staff_name: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AuditEvent(Base):
    """Who did what, for everything that changes an authorisation or a person."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_nursery_time", "nursery_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nursery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nurseries.id"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    subject_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
