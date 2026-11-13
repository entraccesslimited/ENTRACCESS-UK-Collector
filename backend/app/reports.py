"""The manager's numbers, and the evidence pack for an inspection or a review.

Both read the same record the rest of the app writes and change nothing. The
period is in the nursery's own days, at most a quarter at a time.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import reconcile
from app.collection import CollectionError, child_in_nursery, day_bounds, nursery_of, zone
from app.models import (
    AuditEvent,
    Authorisation,
    CheckResult,
    Child,
    CollectorKind,
    CollectorSource,
    DoorCheck,
    Handover,
    HandoverOutcome,
    Restriction,
    SignOutImport,
    User,
)
from app.routers.admin import ACTIONS  # the same words as the activity log

MAX_DAYS = 92


def period(today: date, start: date | None, end: date | None) -> tuple[date, date]:
    last = end or today
    first = start or last - timedelta(days=29)
    if first > last:
        raise CollectionError("The start is after the end.")
    if (last - first).days + 1 > MAX_DAYS:
        raise CollectionError(f"Choose a period of {MAX_DAYS} days or fewer.")
    return first, last


@dataclass(slots=True)
class Kpis:
    start: date
    end: date
    releases: int = 0
    refusals: int = 0
    refusal_reasons: list[tuple[str, int]] = field(default_factory=list)
    blocked_checks: int = 0
    blocked_by_result: dict[str, int] = field(default_factory=dict)
    id_checks: dict[str, int] = field(default_factory=dict)
    collectors_added_by_parents: int = 0
    one_off_collectors: int = 0
    contacts_added_by_nursery: int = 0
    collectors_removed: int = 0
    passes_shared: int = 0
    restrictions_added: int = 0
    restrictions_in_force: int = 0
    days_with_releases: int = 0
    registers_imported: int = 0
    days_without_register: int = 0
    reconciliation_flags: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class Scope:
    nursery_id: uuid.UUID
    since: datetime
    until: datetime
    child: Child | None


async def _scope(
    session: AsyncSession, admin: User, start: date, end: date, child_id: uuid.UUID | None
) -> Scope:
    nursery = await nursery_of(session, admin)
    since, _ = day_bounds(nursery, start)
    _, until = day_bounds(nursery, end)
    child = await child_in_nursery(session, admin, child_id) if child_id else None
    return Scope(admin.nursery_id, since, until, child)


async def _auth_ids(session: AsyncSession, child: Child) -> list[uuid.UUID]:
    return list(
        await session.scalars(select(Authorisation.id).where(Authorisation.child_id == child.id))
    )


async def kpis(
    session: AsyncSession,
    admin: User,
    start: date,
    end: date,
    child_id: uuid.UUID | None = None,
) -> Kpis:
    scope = await _scope(session, admin, start, end, child_id)
    nursery = await nursery_of(session, admin)
    out = Kpis(start=start, end=end)

    handovers = (
        await session.scalars(
            select(Handover).where(
                Handover.nursery_id == scope.nursery_id,
                Handover.occurred_at >= scope.since,
                Handover.occurred_at <= scope.until,
                *([Handover.child_id == scope.child.id] if scope.child else []),
            )
        )
    ).all()
    reasons: Counter[str] = Counter()
    methods: Counter[str] = Counter()
    release_days: set[date] = set()
    tz = zone(nursery)
    for h in handovers:
        if h.outcome is HandoverOutcome.RELEASED:
            out.releases += 1
            methods[h.id_check_method.value if h.id_check_method else "not_recorded"] += 1
            release_days.add(h.occurred_at.astimezone(tz).date())
        else:
            out.refusals += 1
            reasons[(h.refusal_reason or "").strip().capitalize() or "No reason"] += 1
    out.refusal_reasons = reasons.most_common(5)
    out.id_checks = dict(methods)
    out.days_with_releases = len(release_days)

    checks = (
        await session.scalars(
            select(DoorCheck.result).where(
                DoorCheck.nursery_id == scope.nursery_id,
                DoorCheck.checked_at >= scope.since,
                DoorCheck.checked_at <= scope.until,
                DoorCheck.result != CheckResult.VALID,
                *([DoorCheck.child_id == scope.child.id] if scope.child else []),
            )
        )
    ).all()
    blocked = Counter(r.value for r in checks)
    out.blocked_checks = sum(blocked.values())
    out.blocked_by_result = dict(blocked.most_common())

    auths = (
        await session.scalars(
            select(Authorisation).where(
                Authorisation.nursery_id == scope.nursery_id,
                *([Authorisation.child_id == scope.child.id] if scope.child else []),
            )
        )
    ).all()
    for auth in auths:
        if scope.since <= auth.created_at <= scope.until:
            if auth.source is CollectorSource.SETTING:
                out.contacts_added_by_nursery += 1
            else:
                out.collectors_added_by_parents += 1
                if auth.kind is CollectorKind.ONE_OFF:
                    out.one_off_collectors += 1
        if auth.revoked_at and scope.since <= auth.revoked_at <= scope.until:
            out.collectors_removed += 1

    subjects = await _auth_ids(session, scope.child) if scope.child else None
    shared = select(AuditEvent).where(
        AuditEvent.nursery_id == scope.nursery_id,
        AuditEvent.action == "pass.shared",
        AuditEvent.created_at >= scope.since,
        AuditEvent.created_at <= scope.until,
    )
    if subjects is not None:
        shared = shared.where(AuditEvent.subject_id.in_(subjects or [uuid.UUID(int=0)]))
    out.passes_shared = len((await session.scalars(shared)).all())

    restrictions = (
        await session.scalars(
            select(Restriction).where(
                Restriction.nursery_id == scope.nursery_id,
                *([Restriction.child_id == scope.child.id] if scope.child else []),
            )
        )
    ).all()
    for r in restrictions:
        if scope.since <= r.created_at <= scope.until:
            out.restrictions_added += 1
        if r.created_at <= scope.until and (r.ended_at is None or r.ended_at > scope.until):
            out.restrictions_in_force += 1

    imported_days = set(
        (
            await session.scalars(
                select(SignOutImport.day).where(
                    SignOutImport.nursery_id == scope.nursery_id,
                    SignOutImport.day >= start,
                    SignOutImport.day <= end,
                )
            )
        ).all()
    )
    out.registers_imported = len(imported_days)
    out.days_without_register = len(release_days - imported_days)
    flags: Counter[str] = Counter()
    for day in sorted(imported_days):
        for line in (await reconcile.reconcile(session, admin, day)).lines:
            if scope.child and line.child_id != scope.child.id:
                continue
            flags.update(f.value for f in line.flags)
    out.reconciliation_flags = dict(flags)
    return out


@dataclass(slots=True)
class Event:
    at: datetime
    kind: str
    child: str
    detail: str
    who: str


@dataclass(slots=True)
class FlaggedLine:
    day: date
    line: reconcile.Line


@dataclass(slots=True)
class Evidence:
    nursery_name: str
    start: date
    end: date
    child_name: str | None
    generated_at: datetime
    generated_by: str
    kpis: Kpis
    collectors: list[Authorisation]
    collector_names: dict[uuid.UUID, str]
    restrictions: list[Restriction]
    restriction_children: dict[uuid.UUID, str]
    events: list[Event]
    flagged: list[FlaggedLine]
    registers: list[date]


async def evidence(
    session: AsyncSession,
    admin: User,
    start: date,
    end: date,
    child_id: uuid.UUID | None = None,
) -> Evidence:
    """Everything the record holds about collections in a period, for one child or all."""
    scope = await _scope(session, admin, start, end, child_id)
    nursery = await nursery_of(session, admin)
    summary = await kpis(session, admin, start, end, child_id)
    children = {
        c.id: c.full_name
        for c in (
            await session.scalars(select(Child).where(Child.nursery_id == scope.nursery_id))
        ).all()
    }
    users = {
        u.id: u.full_name
        for u in (
            await session.scalars(select(User).where(User.nursery_id == scope.nursery_id))
        ).all()
    }

    # Collectors who could collect at any point in the period.
    auth_query = select(Authorisation).where(
        Authorisation.nursery_id == scope.nursery_id,
        Authorisation.created_at <= scope.until,
        or_(Authorisation.revoked_at.is_(None), Authorisation.revoked_at >= scope.since),
        or_(Authorisation.valid_until.is_(None), Authorisation.valid_until >= scope.since),
    )
    if scope.child:
        auth_query = auth_query.where(Authorisation.child_id == scope.child.id)
    collectors = list((await session.scalars(auth_query.order_by(Authorisation.created_at))).all())

    restriction_query = select(Restriction).where(
        Restriction.nursery_id == scope.nursery_id,
        Restriction.created_at <= scope.until,
        or_(Restriction.ended_at.is_(None), Restriction.ended_at >= scope.since),
    )
    if scope.child:
        restriction_query = restriction_query.where(Restriction.child_id == scope.child.id)
    restrictions = list((await session.scalars(restriction_query)).all())

    events: list[Event] = []
    handover_query = select(Handover).where(
        Handover.nursery_id == scope.nursery_id,
        Handover.occurred_at >= scope.since,
        Handover.occurred_at <= scope.until,
    )
    if scope.child:
        handover_query = handover_query.where(Handover.child_id == scope.child.id)
    for h in (await session.scalars(handover_query)).all():
        if h.outcome is HandoverOutcome.RELEASED:
            method = h.id_check_method.value.replace("_", " ") if h.id_check_method else (
                "checked" if h.id_checked else "not recorded"
            )
            detail = (
                f"Released to {h.collector_name} ({h.collector_relationship}), "
                f"authorised by {h.authorised_by_name}; ID: {method}"
            )
        else:
            detail = f"Not released to {h.collector_name}: {h.refusal_reason}"
        events.append(Event(h.occurred_at, h.outcome.value, h.child_name, detail, h.staff_name))

    check_query = select(DoorCheck).where(
        DoorCheck.nursery_id == scope.nursery_id,
        DoorCheck.checked_at >= scope.since,
        DoorCheck.checked_at <= scope.until,
        DoorCheck.result != CheckResult.VALID,
    )
    if scope.child:
        check_query = check_query.where(DoorCheck.child_id == scope.child.id)
    auth_names = {
        a.id: a.collector_name
        for a in (
            await session.scalars(
                select(Authorisation).where(Authorisation.nursery_id == scope.nursery_id)
            )
        ).all()
    }
    for c in (await session.scalars(check_query)).all():
        who = auth_names.get(c.authorisation_id) if c.authorisation_id else None
        events.append(
            Event(
                c.checked_at,
                "blocked",
                children.get(c.child_id, "") if c.child_id else "",
                f"Check refused: {c.result.value.replace('_', ' ')}"
                + (f" ({who})" if who else ""),
                users.get(c.checked_by_id, "Unknown"),
            )
        )

    audit_query = select(AuditEvent).where(
        AuditEvent.nursery_id == scope.nursery_id,
        AuditEvent.created_at >= scope.since,
        AuditEvent.created_at <= scope.until,
        AuditEvent.action.notin_(["handovers.exported", "evidence.exported", "kpis.exported"]),
    )
    if scope.child:
        ids = [scope.child.id, *await _auth_ids(session, scope.child)]
        audit_query = audit_query.where(AuditEvent.subject_id.in_(ids))
    auth_child = {a.id: a.child_id for a in collectors}
    for e in (await session.scalars(audit_query)).all():
        child_name = ""
        if e.subject_id in children:
            child_name = children[e.subject_id]
        elif e.subject_id in auth_child:
            child_name = children.get(auth_child[e.subject_id], "")
        events.append(
            Event(
                e.created_at,
                e.action.split(".")[0],
                child_name,
                ACTIONS.get(e.action, e.action) + (f": {e.detail}" if e.detail else ""),
                users.get(e.actor_id, "ENTRACCESS UK") if e.actor_id else "ENTRACCESS UK",
            )
        )
    events.sort(key=lambda ev: ev.at)

    registers = sorted(
        set(
            (
                await session.scalars(
                    select(SignOutImport.day).where(
                        SignOutImport.nursery_id == scope.nursery_id,
                        SignOutImport.day >= start,
                        SignOutImport.day <= end,
                    )
                )
            ).all()
        )
    )
    flagged: list[FlaggedLine] = []
    for day in registers:
        for line in (await reconcile.reconcile(session, admin, day)).lines:
            if line.flags and (scope.child is None or line.child_id == scope.child.id):
                flagged.append(FlaggedLine(day, line))

    return Evidence(
        nursery_name=nursery.name,
        start=start,
        end=end,
        child_name=scope.child.full_name if scope.child else None,
        generated_at=datetime.now(UTC),
        generated_by=admin.full_name,
        kpis=summary,
        collectors=collectors,
        collector_names={a.id: children.get(a.child_id, "") for a in collectors},
        restrictions=restrictions,
        restriction_children={r.id: children.get(r.child_id, "") for r in restrictions},
        events=events[:5000],
        flagged=flagged,
        registers=registers,
    )
