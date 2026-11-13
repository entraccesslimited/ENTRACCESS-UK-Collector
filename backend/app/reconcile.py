"""Comparing the door record with the nursery's own sign-out register.

The door record says who was checked and released. The register, kept in the
nursery's management system, says which children left and when. Each catches
what the other misses: a child signed out with no check at the door went home
with someone nobody verified; a release with no sign-out means the register is
wrong, and a fire roll call would count a child who is not there.

A manager exports the day's sign-outs as CSV and imports them here. Nothing in
the register is trusted beyond what it says: children are matched by name, and
a name that matches no child is flagged rather than guessed at.
"""

from __future__ import annotations

import csv
import enum
import io
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import names
from app.collection import CollectionError, audit, day_bounds, nursery_of, zone
from app.models import (
    Child,
    Handover,
    HandoverOutcome,
    IdCheckMethod,
    SignOut,
    SignOutImport,
    User,
)

MAX_BYTES = 1_000_000
MAX_ROWS = 2_000
# A sign-out this far from the release, either way, is worth a look: the
# register was filled in later from memory, or the child left at another time.
TIME_GAP = timedelta(minutes=15)


class Flag(enum.StrEnum):
    # Signed out in the register, but nobody was released the child at the door.
    NO_HANDOVER = "no_handover"
    # Released at the door, but not signed out in the register.
    NO_SIGN_OUT = "no_sign_out"
    # The register names someone other than the collector who was checked.
    COLLECTOR_MISMATCH = "collector_mismatch"
    # The register's time and the release are more than TIME_GAP apart.
    TIME_GAP = "time_gap"
    # The register names a child who is not on our list.
    UNKNOWN_CHILD = "unknown_child"
    # The register signs the child out more than once in the day.
    SIGNED_OUT_TWICE = "signed_out_twice"


# Header spellings seen in nursery system exports, after _key().
CHILD = {"child", "child_name", "childs_name", "name", "full_name", "child_full_name", "pupil"}
FIRST = {"first_name", "forename", "child_first_name", "given_name"}
LAST = {"last_name", "surname", "child_last_name", "family_name"}
TIME = {
    "signed_out",
    "signed_out_at",
    "sign_out",
    "sign_out_time",
    "signed_out_time",
    "time_out",
    "out",
    "out_time",
    "departure",
    "departure_time",
    "departed",
    "check_out",
    "checked_out",
    "checkout",
    "check_out_time",
    "collected_at",
    "collection_time",
    "time",
}
COLLECTOR = {
    "collected_by",
    "collector",
    "picked_up_by",
    "pickup",
    "pick_up",
    "signed_out_by",
    "collection_by",
    "collected",
    "collected_by_name",
    "who_collected",
}
DAY = {"date", "day", "sign_out_date", "attendance_date"}

_CLOCK = re.compile(r"(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?\s*([ap]\.?m\.?)?", re.I)
_ISO_DAY = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_UK_DAY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")


def _key(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", header.strip().lower().replace("'", "")).strip("_")


def _date_in(text: str) -> date | None:
    if found := _ISO_DAY.search(text):
        y, m, d = (int(g) for g in found.groups())
        return date(y, m, d)
    if found := _UK_DAY.search(text):
        d, m, y = (int(g) for g in found.groups())
        return date(y + 2000 if y < 100 else y, m, d)
    return None


def _clock_in(text: str) -> time | None:
    # Skip past a date so its digits are not read as a time.
    rest = _ISO_DAY.sub(" ", _UK_DAY.sub(" ", text))
    found = _CLOCK.search(rest)
    if not found:
        return None
    hour, minute = int(found.group(1)), int(found.group(2))
    second = int(found.group(3) or 0)
    meridiem = (found.group(4) or "").replace(".", "").lower()
    if meridiem:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    if hour > 23 or minute > 59 or second > 59:
        return None
    return time(hour, minute, second)


@dataclass(slots=True)
class ParsedRow:
    line: int
    child_name: str
    clock: time
    collected_by: str | None


def parse(text: str, day: date) -> list[ParsedRow]:
    """Read a register export. Raises CollectionError naming the lines it cannot read."""
    if len(text.encode()) > MAX_BYTES:
        raise CollectionError("That file is too large. Export one day at a time.")
    text = text.lstrip("﻿")
    sample = text[:4096]
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    header = next(reader, None)
    if not header:
        raise CollectionError("The file is empty.")
    keys = [_key(h) for h in header]

    def column(options: set[str]) -> int | None:
        return next((i for i, k in enumerate(keys) if k in options), None)

    child_col, first_col, last_col = column(CHILD), column(FIRST), column(LAST)
    time_col, who_col, day_col = column(TIME), column(COLLECTOR), column(DAY)
    if child_col is None and (first_col is None or last_col is None):
        raise CollectionError(
            "No child's name column found. Name one 'Child', or use 'First name' and 'Surname'."
        )
    if time_col is None:
        raise CollectionError("No sign-out time column found. Name it 'Signed out'.")

    rows: list[ParsedRow] = []
    problems: list[str] = []
    for line, cells in enumerate(reader, start=2):
        if not any(c.strip() for c in cells):
            continue

        def cell(index: int | None, cells: list[str] = cells) -> str:
            return cells[index].strip() if index is not None and index < len(cells) else ""

        child_name = (
            cell(child_col) if child_col is not None else f"{cell(first_col)} {cell(last_col)}"
        )
        child_name = " ".join(child_name.split())
        when = cell(time_col)
        if not child_name or not when:
            # A register lists every child; one with no time has not left.
            continue
        clock = _clock_in(when)
        if clock is None:
            problems.append(f"line {line}: cannot read the time '{when[:40]}'")
            continue
        stated = _date_in(when) or (_date_in(cell(day_col)) if day_col is not None else None)
        if stated is not None and stated != day:
            problems.append(f"line {line}: dated {stated:%d/%m/%Y}, not {day:%d/%m/%Y}")
            continue
        rows.append(ParsedRow(line, child_name[:200], clock, cell(who_col)[:200] or None))
        if len(rows) > MAX_ROWS:
            raise CollectionError(f"More than {MAX_ROWS} sign-outs. Export one day at a time.")
    if problems:
        shown = "; ".join(problems[:5])
        more = f" and {len(problems) - 5} more" if len(problems) > 5 else ""
        raise CollectionError(f"Nothing was imported. Fix these and try again: {shown}{more}.")
    return rows


async def import_register(
    session: AsyncSession, admin: User, day: date, text: str, source: str
) -> SignOutImport:
    nursery = await nursery_of(session, admin)
    if day > datetime.now(zone(nursery)).date():
        raise CollectionError("That day has not happened yet.")
    rows = parse(text, day)
    children = (
        await session.scalars(select(Child).where(Child.nursery_id == admin.nursery_id))
    ).all()
    by_name: dict[str, list[Child]] = defaultdict(list)
    for child in children:
        by_name[names.normalised(child.full_name)].append(child)

    record = SignOutImport(
        nursery_id=admin.nursery_id,
        day=day,
        source=(source.strip() or "CSV")[:200],
        rows=len(rows),
        imported_by_id=admin.id,
    )
    session.add(record)
    await session.flush()
    tz = zone(nursery)
    for row in rows:
        matches = by_name.get(names.normalised(row.child_name), [])
        # Two children with the same name: match neither, and let it be flagged.
        child_id = matches[0].id if len(matches) == 1 else None
        session.add(
            SignOut(
                import_id=record.id,
                nursery_id=admin.nursery_id,
                line=row.line,
                child_name=row.child_name,
                child_id=child_id,
                signed_out_at=datetime.combine(day, row.clock, tzinfo=tz).astimezone(UTC),
                collected_by=row.collected_by,
            )
        )
    await audit(
        session,
        nursery_id=admin.nursery_id,
        actor=admin,
        action="signouts.imported",
        detail=f"{day:%d/%m/%Y}: {len(rows)} sign-outs from {record.source}",
    )
    await session.flush()
    return record


@dataclass(slots=True)
class Line:
    """One child's day, as the door and the register each tell it."""

    child_name: str
    child_id: uuid.UUID | None = None
    signed_out_at: datetime | None = None
    register_collected_by: str | None = None
    released_at: datetime | None = None
    collector_name: str | None = None
    collector_relationship: str | None = None
    staff_name: str | None = None
    id_check_method: IdCheckMethod | None = None
    refusals: list[str] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)


@dataclass(slots=True)
class Reconciliation:
    day: date
    register: SignOutImport | None
    imported_by: str | None
    lines: list[Line]


def _named_the_collector(register: str, handover: Handover) -> bool:
    if names.same_person(register, handover.collector_name):
        return True
    # Registers often hold only a first name or the relationship: "Grace", "Grandma".
    said = names.words(register)
    if len(said) != 1:
        return False
    first = handover.collector_name.split()[0].casefold() if handover.collector_name else ""
    return said <= {first} | names.words(handover.collector_relationship)


async def latest_import(
    session: AsyncSession, nursery_id: uuid.UUID, day: date
) -> SignOutImport | None:
    found: SignOutImport | None = await session.scalar(
        select(SignOutImport)
        .where(SignOutImport.nursery_id == nursery_id, SignOutImport.day == day)
        .order_by(SignOutImport.imported_at.desc())
        .limit(1)
    )
    return found


async def reconcile(session: AsyncSession, admin: User, day: date) -> Reconciliation:
    nursery = await nursery_of(session, admin)
    register = await latest_import(session, admin.nursery_id, day)
    start, end = day_bounds(nursery, day)
    handovers = (
        await session.scalars(
            select(Handover)
            .where(
                Handover.nursery_id == admin.nursery_id,
                Handover.occurred_at >= start,
                Handover.occurred_at <= end,
            )
            .order_by(Handover.occurred_at)
        )
    ).all()
    sign_outs: list[SignOut] = []
    imported_by: str | None = None
    if register is not None:
        sign_outs = list(
            (
                await session.scalars(
                    select(SignOut)
                    .where(SignOut.import_id == register.id)
                    .order_by(SignOut.signed_out_at, SignOut.line)
                )
            ).all()
        )
        who = await session.get(User, register.imported_by_id)
        imported_by = who.full_name if who else None

    tz = zone(nursery)
    lines: list[Line] = []
    released: dict[uuid.UUID, list[Handover]] = defaultdict(list)
    refused: dict[uuid.UUID, list[Handover]] = defaultdict(list)
    names_of: dict[uuid.UUID, str] = {}
    for h in handovers:
        (released if h.outcome is HandoverOutcome.RELEASED else refused)[h.child_id].append(h)
        names_of[h.child_id] = h.child_name
    signed: dict[uuid.UUID, list[SignOut]] = defaultdict(list)
    for s in sign_outs:
        if s.child_id is None:
            lines.append(
                Line(
                    child_name=s.child_name,
                    signed_out_at=s.signed_out_at,
                    register_collected_by=s.collected_by,
                    flags=[Flag.UNKNOWN_CHILD],
                )
            )
        else:
            signed[s.child_id].append(s)
            names_of.setdefault(s.child_id, s.child_name)

    # With no register yet there is nothing to compare: show the door's side only.
    for child_id in released.keys() | (signed.keys() if register is not None else set()):
        outs, rels = signed.get(child_id, []), released.get(child_id, [])
        child = await session.get(Child, child_id)
        line = Line(child_name=child.full_name if child else names_of[child_id], child_id=child_id)
        line.refusals = [
            f"{r.occurred_at.astimezone(tz):%H:%M} {r.collector_name}: {r.refusal_reason}"
            for r in refused.get(child_id, [])
        ]
        if outs:
            line.signed_out_at = outs[0].signed_out_at
            line.register_collected_by = outs[0].collected_by
        if rels:
            h = rels[0]
            line.released_at = h.occurred_at
            line.collector_name = h.collector_name
            line.collector_relationship = h.collector_relationship
            line.staff_name = h.staff_name
            line.id_check_method = h.id_check_method
        if register is not None:
            if outs and not rels:
                line.flags.append(Flag.NO_HANDOVER)
            if rels and not outs:
                line.flags.append(Flag.NO_SIGN_OUT)
            if outs and rels:
                if line.register_collected_by and not _named_the_collector(
                    line.register_collected_by, rels[0]
                ):
                    line.flags.append(Flag.COLLECTOR_MISMATCH)
                if abs(outs[0].signed_out_at - rels[0].occurred_at) > TIME_GAP:
                    line.flags.append(Flag.TIME_GAP)
            if len(outs) > 1:
                line.flags.append(Flag.SIGNED_OUT_TWICE)
        lines.append(line)

    def order(line: Line) -> tuple[int, datetime]:
        moment = line.signed_out_at or line.released_at or start
        return (0 if line.flags else 1, moment)

    lines.sort(key=order)
    return Reconciliation(day=day, register=register, imported_by=imported_by, lines=lines)
