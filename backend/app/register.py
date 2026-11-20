"""The arrival register: who is in today, and who is not expected.

Staff mark each child in when they arrive. The door phone may have no
signal, so a mark can be made offline and sent later: it carries the time it
was made and its own id, and the server records it on the day it was made,
once, however many times it is sent. A child is marked in at most once a day.

Parents (or staff, for a phoned-in absence) can say ahead of time that a child
will be off. Together with the days a child is booked in, that is what lets
the morning's non-arrival check tell parents only about a child who really was
expected and has not appeared.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collection import (
    CollectionError,
    audit,
    child_for_parent,
    child_in_nursery,
    day_bounds,
    local_date,
    nursery_of,
)
from app.models import (
    Absence,
    AbsenceReason,
    Arrival,
    Child,
    Handover,
    HandoverOutcome,
    Nursery,
    Role,
    User,
)

# A mark made offline is accepted for this long after it was made: a phone
# that was offline all day still sends the morning's register that evening.
OFFLINE_GRACE = timedelta(hours=36)
CLOCK_SKEW = timedelta(minutes=5)
ABSENCE_DAYS_AHEAD = 60
DAY_LETTERS = "1234567"


def expected_on(child: Child, day: date) -> bool:
    return str(day.isoweekday()) in (child.session_days or "")


def valid_session_days(days: str) -> str:
    cleaned = "".join(sorted(set(days)))
    if not cleaned or any(d not in DAY_LETTERS for d in cleaned):
        raise CollectionError("Choose the days the child attends.")
    return cleaned


@dataclass(slots=True)
class RegisterRow:
    child: Child
    expected: bool
    arrival: Arrival | None
    absence: Absence | None
    collected: Handover | None


async def active_absence(session: AsyncSession, child_id: uuid.UUID, day: date) -> Absence | None:
    found: Absence | None = await session.scalar(
        select(Absence).where(
            Absence.child_id == child_id, Absence.day == day, Absence.cancelled_at.is_(None)
        )
    )
    return found


async def register_for(session: AsyncSession, nursery: Nursery, day: date) -> list[RegisterRow]:
    children = (
        await session.scalars(
            select(Child)
            .where(Child.nursery_id == nursery.id, Child.active.is_(True))
            .order_by(Child.full_name)
        )
    ).all()
    arrivals = {
        a.child_id: a
        for a in (
            await session.scalars(
                select(Arrival).where(Arrival.nursery_id == nursery.id, Arrival.day == day)
            )
        ).all()
    }
    absences = {
        a.child_id: a
        for a in (
            await session.scalars(
                select(Absence).where(
                    Absence.nursery_id == nursery.id,
                    Absence.day == day,
                    Absence.cancelled_at.is_(None),
                )
            )
        ).all()
    }
    start, end = day_bounds(nursery, day)
    released: dict[uuid.UUID, Handover] = {}
    for h in (
        await session.scalars(
            select(Handover)
            .where(
                Handover.nursery_id == nursery.id,
                Handover.outcome == HandoverOutcome.RELEASED,
                Handover.occurred_at.between(start, end),
            )
            .order_by(Handover.occurred_at)
        )
    ).all():
        released.setdefault(h.child_id, h)
    return [
        RegisterRow(
            child=c,
            expected=expected_on(c, day),
            arrival=arrivals.get(c.id),
            absence=absences.get(c.id),
            collected=released.get(c.id),
        )
        for c in children
    ]


@dataclass(frozen=True, slots=True)
class Marked:
    arrival: Arrival | None
    # recorded: new; duplicate: this same mark was sent before;
    # already: the child was already marked in that day by another mark.
    status: str


async def mark_arrival(
    session: AsyncSession,
    staff: User,
    child_id: uuid.UUID,
    *,
    occurred_at: datetime | None = None,
    client_id: str | None = None,
    offline: bool = False,
) -> Marked:
    now = datetime.now(UTC)
    if client_id:
        seen = await session.scalar(select(Arrival).where(Arrival.client_id == client_id))
        if seen is not None:
            if seen.nursery_id != staff.nursery_id:
                raise CollectionError("That mark belongs to another nursery.", status=409)
            return Marked(seen, "duplicate")
    child = await child_in_nursery(session, staff, child_id)
    if not child.active:
        raise CollectionError(f"{child.full_name} has left the nursery.")
    when = now if occurred_at is None else occurred_at
    if when.tzinfo is None:
        raise CollectionError("A mark must say its time zone.")
    when = when.astimezone(UTC)
    if when > now + CLOCK_SKEW:
        raise CollectionError("That mark is timed in the future. Check the phone's clock.")
    if when < now - OFFLINE_GRACE:
        raise CollectionError("That mark is too old to record. Tell the manager.")
    when = min(when, now)
    nursery = await nursery_of(session, staff)
    day = local_date(nursery, when)
    existing = await session.scalar(
        select(Arrival).where(Arrival.child_id == child.id, Arrival.day == day)
    )
    if existing is not None:
        return Marked(existing, "already")
    arrival = Arrival(
        nursery_id=staff.nursery_id,
        child_id=child.id,
        day=day,
        arrived_at=when,
        recorded_by_id=staff.id,
        recorded_offline=offline,
        client_id=client_id or None,
    )
    session.add(arrival)
    await session.flush()
    return Marked(arrival, "recorded")


async def undo_arrival(session: AsyncSession, staff: User, child_id: uuid.UUID) -> None:
    """Take back a mark made by mistake today. Logged, so it is never silent."""
    child = await child_in_nursery(session, staff, child_id)
    nursery = await nursery_of(session, staff)
    day = local_date(nursery, datetime.now(UTC))
    arrival = await session.scalar(
        select(Arrival).where(Arrival.child_id == child.id, Arrival.day == day)
    )
    if arrival is None:
        raise CollectionError(f"{child.full_name} is not marked in today.", status=404)
    await session.delete(arrival)
    await audit(
        session,
        nursery_id=staff.nursery_id,
        actor=staff,
        action="arrival.undone",
        subject_id=child.id,
        detail=child.full_name,
    )


async def report_absence(
    session: AsyncSession,
    user: User,
    child_id: uuid.UUID,
    day: date,
    reason: AbsenceReason,
    note: str | None,
) -> Absence:
    child = (
        await child_for_parent(session, user, child_id)
        if user.role is Role.PARENT
        else await child_in_nursery(session, user, child_id)
    )
    nursery = await nursery_of(session, user)
    today = local_date(nursery, datetime.now(UTC))
    if day < today:
        raise CollectionError("That day has already passed.")
    if day > today + timedelta(days=ABSENCE_DAYS_AHEAD):
        raise CollectionError(f"An absence can be given up to {ABSENCE_DAYS_AHEAD} days ahead.")
    if day == today:
        arrived = await session.scalar(
            select(Arrival).where(Arrival.child_id == child.id, Arrival.day == day)
        )
        if arrived is not None:
            raise CollectionError(f"{child.full_name} has already arrived today.")
    absence = await active_absence(session, child.id, day)
    if absence is None:
        absence = Absence(
            nursery_id=child.nursery_id,
            child_id=child.id,
            day=day,
            reason=reason,
            note=(note or "").strip() or None,
            reported_by_id=user.id,
        )
        session.add(absence)
    else:
        absence.reason, absence.note = reason, (note or "").strip() or None
    await session.flush()
    await audit(
        session,
        nursery_id=child.nursery_id,
        actor=user,
        action="absence.reported",
        subject_id=child.id,
        detail=f"{child.full_name} off on {day:%d %b %Y} ({reason.value})",
    )
    return absence


async def cancel_absence(session: AsyncSession, user: User, absence_id: uuid.UUID) -> Absence:
    absence = await session.scalar(
        select(Absence).where(Absence.id == absence_id, Absence.nursery_id == user.nursery_id)
    )
    if absence is None:
        raise CollectionError("No such absence.", status=404)
    if user.role is Role.PARENT:
        await child_for_parent(session, user, absence.child_id)
    if absence.cancelled_at is None:
        absence.cancelled_at = datetime.now(UTC)
        await audit(
            session,
            nursery_id=user.nursery_id,
            actor=user,
            action="absence.cancelled",
            subject_id=absence.child_id,
            detail=f"{absence.day:%d %b %Y}",
        )
    return absence


async def upcoming_absences(
    session: AsyncSession, nursery: Nursery, child_id: uuid.UUID
) -> list[Absence]:
    today = local_date(nursery, datetime.now(UTC))
    rows = await session.scalars(
        select(Absence)
        .where(Absence.child_id == child_id, Absence.day >= today, Absence.cancelled_at.is_(None))
        .order_by(Absence.day)
    )
    return list(rows.all())
