"""Authorising collectors, checking them at the door, and recording handovers.

The rules live here rather than in the routes, because they are the product:

* Only a parent linked to a child may authorise someone to collect that child.
* A one-off collector is good for one collection inside a window of at most a
  week. Once the child is released to them, the pass and code stop working.
* A regular collector is good every day inside their window, with a code that
  changes each day.
* Revoking is instant and final. Reissuing gives a new pass and code and stops
  the old ones at once.
* Every check at the door is recorded, whatever its answer. A release or a
  refusal can only follow a check that came back valid, and is re-checked at
  the moment it is made, so a collector revoked while standing at the door is
  not released.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import geofence, passes
from app.config import get_settings
from app.models import (
    AuditEvent,
    Authorisation,
    CheckMethod,
    CheckResult,
    Child,
    CollectorKind,
    DoorCheck,
    Handover,
    HandoverOutcome,
    Nursery,
    ParentLink,
    User,
)
from app.notify import notify_parents

MAX_ACTIVE_PER_CHILD = 12
MAX_ONE_OFF_DAYS = 7
DECISION_WINDOW = timedelta(minutes=10)


class CollectionError(ValueError):
    """A request the rules refuse. The message is safe to show."""

    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _aware(moment: datetime) -> datetime:
    # SQLite hands back naive datetimes; everything here is stored in UTC.
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def zone(nursery: Nursery) -> ZoneInfo:
    return ZoneInfo(nursery.timezone or get_settings().DEFAULT_TIMEZONE)


def local_date(nursery: Nursery, moment: datetime) -> date:
    return _aware(moment).astimezone(zone(nursery)).date()


def local_time(nursery: Nursery, moment: datetime) -> datetime:
    return _aware(moment).astimezone(zone(nursery))


def day_bounds(nursery: Nursery, day: date) -> tuple[datetime, datetime]:
    tz = zone(nursery)
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day, time(23, 59, 59), tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def status_of(auth: Authorisation, now: datetime) -> CheckResult:
    """Whether an authorisation can be used right now, and if not, why not."""
    if auth.revoked_at is not None:
        return CheckResult.REVOKED
    if auth.used_at is not None:
        return CheckResult.ALREADY_USED
    if now < _aware(auth.valid_from):
        return CheckResult.NOT_YET_VALID
    if auth.valid_until is not None and now > _aware(auth.valid_until):
        return CheckResult.EXPIRED
    return CheckResult.VALID


async def audit(
    session: AsyncSession,
    *,
    nursery_id: uuid.UUID,
    actor: User | None,
    action: str,
    subject_id: uuid.UUID | None = None,
    detail: str | None = None,
) -> None:
    session.add(
        AuditEvent(
            nursery_id=nursery_id,
            actor_id=actor.id if actor else None,
            action=action,
            subject_id=subject_id,
            detail=detail,
        )
    )


async def nursery_of(session: AsyncSession, user: User) -> Nursery:
    nursery = await session.get(Nursery, user.nursery_id)
    assert nursery is not None
    return nursery


async def child_for_parent(session: AsyncSession, parent: User, child_id: uuid.UUID) -> Child:
    child = await session.scalar(
        select(Child)
        .join(ParentLink, ParentLink.child_id == Child.id)
        .where(
            ParentLink.parent_id == parent.id,
            Child.id == child_id,
            Child.nursery_id == parent.nursery_id,
        )
    )
    if child is None:
        raise CollectionError("No such child on your account.", status=404)
    return child


async def child_in_nursery(session: AsyncSession, user: User, child_id: uuid.UUID) -> Child:
    child = await session.scalar(
        select(Child).where(Child.id == child_id, Child.nursery_id == user.nursery_id)
    )
    if child is None:
        raise CollectionError("No such child at this nursery.", status=404)
    return child


@dataclass(frozen=True, slots=True)
class NewAuthorisation:
    collector_name: str
    collector_relationship: str
    collector_phone: str
    kind: CollectorKind
    note_for_staff: str | None = None
    # One-off: the day of the collection, and optionally a narrower window.
    on_date: date | None = None
    from_time: time | None = None
    until_time: time | None = None
    # Regular: optional first and last day.
    start_date: date | None = None
    end_date: date | None = None


def _window(
    nursery: Nursery, data: NewAuthorisation, now: datetime
) -> tuple[datetime, datetime | None]:
    tz = zone(nursery)
    today = local_date(nursery, now)
    if data.kind is CollectorKind.ONE_OFF:
        if data.on_date is None:
            raise CollectionError("Choose the day of the collection.")
        if data.on_date < today:
            raise CollectionError("That day has already passed.")
        if data.on_date > today + timedelta(days=MAX_ONE_OFF_DAYS):
            raise CollectionError(
                f"A one-off collection can be set up to {MAX_ONE_OFF_DAYS} days ahead."
            )
        opens = datetime.combine(data.on_date, data.from_time or time.min, tzinfo=tz)
        closes = datetime.combine(data.on_date, data.until_time or time(23, 59, 59), tzinfo=tz)
        if closes <= opens:
            raise CollectionError("The end of the window must be after its start.")
        return opens.astimezone(UTC), closes.astimezone(UTC)

    first = data.start_date or today
    if first < today:
        raise CollectionError("The first day cannot be in the past.")
    start = datetime.combine(first, time.min, tzinfo=tz).astimezone(UTC)
    if first == today:
        start = min(start, now)
    end: datetime | None = None
    if data.end_date is not None:
        if data.end_date < first:
            raise CollectionError("The last day must be on or after the first day.")
        end = datetime.combine(data.end_date, time(23, 59, 59), tzinfo=tz).astimezone(UTC)
    return start, end


async def authorise(
    session: AsyncSession, parent: User, child_id: uuid.UUID, data: NewAuthorisation
) -> Authorisation:
    child = await child_for_parent(session, parent, child_id)
    nursery = await nursery_of(session, parent)
    now = datetime.now(UTC)

    name = data.collector_name.strip()
    phone = data.collector_phone.strip()
    if len(name) < 2:
        raise CollectionError("Give the collector's full name.")
    if len("".join(ch for ch in phone if ch.isdigit())) < 7:
        raise CollectionError("Give a phone number staff can ring.")

    active = await session.scalar(
        select(func.count())
        .select_from(Authorisation)
        .where(
            Authorisation.child_id == child.id,
            Authorisation.revoked_at.is_(None),
            Authorisation.used_at.is_(None),
        )
    )
    if (active or 0) >= MAX_ACTIVE_PER_CHILD:
        raise CollectionError(
            f"{child.full_name} already has {MAX_ACTIVE_PER_CHILD} active collectors. "
            "Remove one before adding another."
        )

    valid_from, valid_until = _window(nursery, data, now)
    auth = Authorisation(
        nursery_id=parent.nursery_id,
        child_id=child.id,
        authorised_by_id=parent.id,
        collector_name=name,
        collector_relationship=data.collector_relationship.strip() or "Other",
        collector_phone=phone,
        note_for_staff=(data.note_for_staff or "").strip() or None,
        kind=data.kind,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.add(auth)
    await session.flush()
    await audit(
        session,
        nursery_id=parent.nursery_id,
        actor=parent,
        action="authorisation.created",
        subject_id=auth.id,
        detail=f"{data.kind.value} collector {name} for {child.full_name}",
    )
    return auth


async def authorisation_for_parent(
    session: AsyncSession, parent: User, authorisation_id: uuid.UUID
) -> Authorisation:
    auth = await session.scalar(
        select(Authorisation)
        .join(ParentLink, ParentLink.child_id == Authorisation.child_id)
        .where(
            Authorisation.id == authorisation_id,
            Authorisation.nursery_id == parent.nursery_id,
            ParentLink.parent_id == parent.id,
        )
    )
    if auth is None:
        raise CollectionError("No such collector on your account.", status=404)
    return auth


async def revoke(session: AsyncSession, actor: User, auth: Authorisation) -> Authorisation:
    if auth.revoked_at is None:
        auth.revoked_at = datetime.now(UTC)
        auth.revoked_by_id = actor.id
        await audit(
            session,
            nursery_id=auth.nursery_id,
            actor=actor,
            action="authorisation.revoked",
            subject_id=auth.id,
            detail=auth.collector_name,
        )
    return auth


async def reissue(session: AsyncSession, actor: User, auth: Authorisation) -> Authorisation:
    if auth.revoked_at is not None:
        raise CollectionError("This collector has been removed. Add them again instead.")
    if auth.used_at is not None:
        raise CollectionError("This one-off collection has happened. Add a new one instead.")
    auth.version += 1
    await audit(
        session,
        nursery_id=auth.nursery_id,
        actor=actor,
        action="authorisation.reissued",
        subject_id=auth.id,
        detail=f"version {auth.version}",
    )
    return auth


def pass_for(auth: Authorisation) -> str:
    return passes.issue_pass(auth.nursery_id, auth.id, auth.version)


def code_for(nursery: Nursery, auth: Authorisation, now: datetime) -> str:
    return passes.daily_code(auth.nursery_id, auth.id, auth.version, local_date(nursery, now))


def fence_of(nursery: Nursery) -> geofence.Fence | None:
    if (
        nursery.geofence_latitude is None
        or nursery.geofence_longitude is None
        or nursery.geofence_radius_m is None
    ):
        return None
    return geofence.Fence(
        nursery.geofence_latitude, nursery.geofence_longitude, nursery.geofence_radius_m
    )


async def _record(
    session: AsyncSession,
    staff: User,
    *,
    method: CheckMethod,
    result: CheckResult,
    child_id: uuid.UUID | None = None,
    auth: Authorisation | None = None,
    position: geofence.Position | None = None,
    distance: float | None = None,
) -> DoorCheck:
    check = DoorCheck(
        nursery_id=staff.nursery_id,
        checked_by_id=staff.id,
        method=method,
        result=result,
        child_id=child_id or (auth.child_id if auth else None),
        authorisation_id=auth.id if auth else None,
        latitude=position.latitude if position else None,
        longitude=position.longitude if position else None,
        accuracy_m=position.accuracy_m if position else None,
        distance_m=round(distance, 1) if distance is not None else None,
    )
    session.add(check)
    await session.flush()
    return check


async def _fenced_out(
    session: AsyncSession,
    staff: User,
    method: CheckMethod,
    position: geofence.Position | None,
    child_id: uuid.UUID | None = None,
) -> tuple[DoorCheck | None, float | None]:
    """Refuse and record a check from outside the nursery's geofence.

    Decided before the pass or code is even looked at, so a phone off the
    premises learns nothing about whether what it holds is valid.
    """
    nursery = await nursery_of(session, staff)
    verdict = geofence.check(fence_of(nursery), position)
    if verdict.allowed:
        return None, verdict.distance_m
    result = (
        CheckResult.NO_LOCATION
        if verdict.verdict is geofence.Verdict.UNKNOWN
        else CheckResult.OUTSIDE_GEOFENCE
    )
    check = await _record(
        session,
        staff,
        method=method,
        result=result,
        child_id=child_id,
        position=position,
        distance=verdict.distance_m,
    )
    return check, verdict.distance_m


async def check_pass(
    session: AsyncSession, staff: User, token: str, position: geofence.Position | None = None
) -> DoorCheck:
    refused, distance = await _fenced_out(session, staff, CheckMethod.PASS, position)
    if refused is not None:
        return refused
    where: dict[str, Any] = {"position": position, "distance": distance}
    try:
        payload = passes.read_pass(token, nursery_id=staff.nursery_id)
    except passes.InvalidPass:
        result = (
            CheckResult.UNREADABLE
            if not token.strip().startswith("CP1.")
            else (CheckResult.WRONG_NURSERY)
        )
        return await _record(session, staff, method=CheckMethod.PASS, result=result, **where)

    auth = await session.scalar(
        select(Authorisation).where(
            Authorisation.id == payload.authorisation_id,
            Authorisation.nursery_id == staff.nursery_id,
        )
    )
    if auth is None:
        return await _record(
            session, staff, method=CheckMethod.PASS, result=CheckResult.UNKNOWN, **where
        )
    if payload.version != auth.version:
        return await _record(
            session, staff, method=CheckMethod.PASS, result=CheckResult.REISSUED, auth=auth, **where
        )
    now = datetime.now(UTC)
    result = await _unless_collected(session, staff, auth, status_of(auth, now), now)
    return await _record(session, staff, method=CheckMethod.PASS, result=result, auth=auth, **where)


async def released_today(
    session: AsyncSession, nursery: Nursery, child_id: uuid.UUID, now: datetime
) -> Handover | None:
    """The handover that already released this child today, if there is one.

    "Today" is the nursery's own day. A refusal does not count: the child is
    still at the nursery after one.
    """
    start, end = day_bounds(nursery, local_date(nursery, now))
    found: Handover | None = await session.scalar(
        select(Handover)
        .where(
            Handover.child_id == child_id,
            Handover.outcome == HandoverOutcome.RELEASED,
            Handover.occurred_at >= start,
            Handover.occurred_at <= end,
        )
        .order_by(Handover.occurred_at.desc())
        .limit(1)
    )
    return found


async def _unless_collected(
    session: AsyncSession, staff: User, auth: Authorisation, result: CheckResult, now: datetime
) -> CheckResult:
    """A valid collector is still refused for a child who has already gone home."""
    if result is not CheckResult.VALID:
        return result
    nursery = await nursery_of(session, staff)
    if await released_today(session, nursery, auth.child_id, now) is not None:
        return CheckResult.ALREADY_COLLECTED
    return result


async def _recent_wrong_codes(session: AsyncSession, child_id: uuid.UUID) -> int:
    settings = get_settings()
    since = datetime.now(UTC) - timedelta(minutes=settings.CODE_ATTEMPT_WINDOW_MINUTES)
    count = await session.scalar(
        select(func.count())
        .select_from(DoorCheck)
        .where(
            DoorCheck.child_id == child_id,
            DoorCheck.method == CheckMethod.CODE,
            DoorCheck.result.in_([CheckResult.WRONG_CODE, CheckResult.LOCKED]),
            DoorCheck.checked_at >= since,
        )
    )
    return int(count or 0)


async def check_code(
    session: AsyncSession,
    staff: User,
    child_id: uuid.UUID,
    code: str,
    position: geofence.Position | None = None,
) -> DoorCheck:
    """Check a six-digit code against every current collector for one child.

    Codes are tried against one child, never against the whole nursery: six
    digits across a hundred collectors would be guessable, and against one
    child's handful it is not — especially with entry paused after a few
    wrong tries.
    """
    child = await child_in_nursery(session, staff, child_id)
    refused, distance = await _fenced_out(
        session, staff, CheckMethod.CODE, position, child_id=child.id
    )
    if refused is not None:
        return refused
    where: dict[str, Any] = {"position": position, "distance": distance}
    if await _recent_wrong_codes(session, child.id) >= get_settings().CODE_ATTEMPT_LIMIT:
        return await _record(
            session,
            staff,
            method=CheckMethod.CODE,
            result=CheckResult.LOCKED,
            child_id=child.id,
            **where,
        )

    nursery = await nursery_of(session, staff)
    now = datetime.now(UTC)
    candidates = (
        await session.scalars(select(Authorisation).where(Authorisation.child_id == child.id))
    ).all()
    for auth in candidates:
        if passes.codes_match(code, code_for(nursery, auth, now)):
            return await _record(
                session,
                staff,
                method=CheckMethod.CODE,
                result=await _unless_collected(session, staff, auth, status_of(auth, now), now),
                auth=auth,
                **where,
            )
    return await _record(
        session,
        staff,
        method=CheckMethod.CODE,
        result=CheckResult.WRONG_CODE,
        child_id=child.id,
        **where,
    )


async def decide(
    session: AsyncSession,
    staff: User,
    check_id: uuid.UUID,
    *,
    release: bool,
    reason: str | None,
    id_checked: bool = False,
) -> Handover:
    check = await session.scalar(
        select(DoorCheck).where(DoorCheck.id == check_id, DoorCheck.nursery_id == staff.nursery_id)
    )
    if check is None:
        raise CollectionError("No such check.", status=404)
    if check.result is not CheckResult.VALID or check.authorisation_id is None:
        raise CollectionError("Only a valid check can lead to a handover.", status=409)
    already = await session.scalar(select(Handover).where(Handover.door_check_id == check.id))
    if already is not None:
        raise CollectionError("This check has already been decided.", status=409)
    now = datetime.now(UTC)
    if now - _aware(check.checked_at) > DECISION_WINDOW:
        raise CollectionError("This check is too old. Check the collector again.", status=409)

    auth = await session.get(Authorisation, check.authorisation_id)
    child = await session.get(Child, check.child_id) if check.child_id else None
    assert auth is not None and child is not None
    parent = await session.get(User, auth.authorised_by_id)

    if release and status_of(auth, now) is not CheckResult.VALID:
        raise CollectionError(
            "This collector stopped being authorised after the check. Do not release the child.",
            status=409,
        )
    if release:
        # Checked again here, not only at the door check: two members of staff
        # can check two collectors for the same child a minute apart.
        nursery = await nursery_of(session, staff)
        earlier = await released_today(session, nursery, child.id, now)
        if earlier is not None:
            raise CollectionError(
                f"{child.full_name} was already collected at "
                f"{local_time(nursery, earlier.occurred_at):%H:%M} by "
                f"{earlier.collector_name}. Do not release.",
                status=409,
            )
    if release and not id_checked:
        raise CollectionError(
            "Confirm the ID check first: photo ID seen, or the collector is known to you."
        )
    if not release and not (reason or "").strip():
        raise CollectionError("Say why the child was not released.")

    handover = Handover(
        nursery_id=staff.nursery_id,
        door_check_id=check.id,
        child_id=child.id,
        authorisation_id=auth.id,
        outcome=HandoverOutcome.RELEASED if release else HandoverOutcome.REFUSED,
        refusal_reason=None if release else (reason or "").strip(),
        child_name=child.full_name,
        collector_name=auth.collector_name,
        collector_relationship=auth.collector_relationship,
        authorised_by_name=parent.full_name if parent else "Unknown",
        staff_id=staff.id,
        staff_name=staff.full_name,
        id_checked=id_checked,
        occurred_at=now,
    )
    session.add(handover)
    if release and auth.kind is CollectorKind.ONE_OFF:
        auth.used_at = now
    await session.flush()
    await notify_parents(session, handover)
    return handover
