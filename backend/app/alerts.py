"""Same-morning non-arrival alerts.

At the time a nursery chooses, every child booked in today who has not been
marked in, has no absence given and has not already gone home is a child a
parent may want to know about. Each of their parents is emailed once.

A missing child and a register nobody took look the same in the data, and
emailing every family because a member of staff was busy would teach parents
to ignore the alert. So the morning is checked first: if nobody at all has
been marked in, or most of the children expected are missing, no parent is
emailed and the managers are told the register looks untaken instead.

The check runs once per nursery per day, inside a few hours of the chosen
time, so a server restarted in the afternoon does not send a morning alert.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import notify, register
from app.collection import local_time
from app.models import (
    Child,
    NonArrivalAlert,
    NonArrivalRun,
    Nursery,
    ParentLink,
    Role,
    User,
)

log = logging.getLogger("collector.alerts")

LATEST_AFTER_ALERT_TIME = timedelta(hours=4)
# Above this share of expected children missing, the register is more likely
# untaken than the children all absent: tell the managers, not the parents.
MOST_MISSING = 0.6
MOST_MISSING_MINIMUM = 5


def due(nursery: Nursery, now: datetime) -> date | None:
    """The day to check, if this nursery's alert is due now."""
    if not nursery.active or nursery.arrival_alert_at is None:
        return None
    local = local_time(nursery, now)
    alert_at = datetime.combine(local.date(), nursery.arrival_alert_at, tzinfo=local.tzinfo)
    if alert_at <= local < alert_at + LATEST_AFTER_ALERT_TIME:
        return local.date()
    return None


def _suppression(expected: int, arrived: int, missing: int) -> str | None:
    if expected and arrived == 0:
        return (
            "Nobody had been marked in, so the register may not have been taken. "
            "No parent was emailed."
        )
    if expected >= MOST_MISSING_MINIMUM and missing / expected > MOST_MISSING:
        return (
            f"{missing} of {expected} children expected were not marked in, which looks like "
            "a register not taken rather than absences. No parent was emailed."
        )
    return None


async def _parents(session: AsyncSession, child: Child) -> list[User]:
    rows = await session.scalars(
        select(User)
        .join(ParentLink, ParentLink.parent_id == User.id)
        .where(ParentLink.child_id == child.id, User.active.is_(True))
    )
    return list(rows.all())


async def _managers(session: AsyncSession, nursery: Nursery) -> list[User]:
    rows = await session.scalars(
        select(User).where(
            User.nursery_id == nursery.id, User.role == Role.ADMIN, User.active.is_(True)
        )
    )
    return list(rows.all())


def _cutoff(nursery: Nursery) -> str:
    at = nursery.arrival_alert_at or dtime(9, 30)
    return f"{at:%H:%M}"


async def run_for(
    session: AsyncSession, nursery: Nursery, day: date, now: datetime
) -> NonArrivalRun | None:
    """Check one nursery's morning. Returns None if it was already checked."""
    already = await session.scalar(
        select(NonArrivalRun).where(
            NonArrivalRun.nursery_id == nursery.id, NonArrivalRun.day == day
        )
    )
    if already is not None:
        return None
    rows = await register.register_for(session, nursery, day)
    expected_rows = [r for r in rows if r.expected and r.absence is None and r.collected is None]
    arrived = sum(1 for r in rows if r.arrival is not None)
    missing = [r for r in expected_rows if r.arrival is None]
    reason = _suppression(len(expected_rows), arrived, len(missing))
    run = NonArrivalRun(
        nursery_id=nursery.id,
        day=day,
        ran_at=now,
        expected=len(expected_rows),
        missing=len(missing),
        alerted=0,
        suppressed_reason=reason,
    )
    session.add(run)
    await session.flush()

    cutoff = _cutoff(nursery)
    if reason is not None:
        for manager in await _managers(session, nursery):
            await notify.send(
                manager.email,
                f"Register check at {nursery.name}: no alerts sent",
                f"The non-arrival check ran at {cutoff} today ({day:%A %d %B}).\n\n{reason}\n\n"
                "If children are in, mark them in on the door app's Register. If the register "
                "is taken later, nothing more is sent today.",
            )
        return run

    nobody_to_tell: list[str] = []
    for row in missing:
        parents = await _parents(session, row.child)
        first = row.child.full_name.split()[0]
        for parent in parents:
            await notify.send(
                parent.email,
                f"{row.child.full_name} has not been marked in at {nursery.name}",
                f"No arrival had been recorded for {row.child.full_name} at {nursery.name} "
                f"by {cutoff} today ({day:%A %d %B}).\n\n"
                f"If {first} is off today, you can tell the nursery in the app. If you "
                f"expected {first} to be there, please call the nursery now.\n\n"
                f"This is what the nursery's register shows. If {first} arrived and was not "
                "marked in, the nursery will correct it.",
            )
        session.add(
            NonArrivalAlert(
                nursery_id=nursery.id,
                child_id=row.child.id,
                day=day,
                sent_at=now,
                parents=len(parents),
            )
        )
        if parents:
            run.alerted += 1
        else:
            nobody_to_tell.append(row.child.full_name)
    if nobody_to_tell:
        # No parent account is linked, so the app cannot tell anyone: the
        # managers can, from the child's registration form.
        for manager in await _managers(session, nursery):
            await notify.send(
                manager.email,
                f"Not marked in at {nursery.name}, and no parent to tell",
                f"These children were booked in today ({day:%A %d %B}) and had not been marked "
                f"in by {cutoff}, but no parent is linked to them in the app, so nobody was "
                "emailed:\n\n"
                + "\n".join(f"  {name}" for name in nobody_to_tell)
                + "\n\nPlease contact their families from the registration forms.",
            )
    return run


async def run_due(session: AsyncSession, now: datetime | None = None) -> list[NonArrivalRun]:
    now = now or datetime.now(UTC)
    runs: list[NonArrivalRun] = []
    for nursery in (
        await session.scalars(select(Nursery).where(Nursery.arrival_alert_at.is_not(None)))
    ).all():
        day = due(nursery, now)
        if day is None:
            continue
        run = await run_for(session, nursery, day, now)
        if run is not None:
            log.info(
                "non-arrival check %s %s: expected %s missing %s alerted %s%s",
                nursery.slug,
                day,
                run.expected,
                run.missing,
                run.alerted,
                " (suppressed)" if run.suppressed_reason else "",
            )
            runs.append(run)
    return runs
