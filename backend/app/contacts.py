"""Collectors the nursery already holds, from its registration forms.

Every setting asks parents at registration who may collect their child. Those
names are entered here once, by a manager, singly or from a CSV, as regular
collectors. Parents are told about each one and can remove any of them; one
on a child's never-release list cannot be added.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import names
from app.collection import (
    MAX_ACTIVE_PER_CHILD,
    CollectionError,
    NewAuthorisation,
    add_contact,
    audit,
    nursery_of,
    restriction_for,
)
from app.models import Authorisation, Child, CollectorKind, Nursery, ParentLink, User
from app.notify import send

MAX_BYTES = 500_000
MAX_ROWS = 2_000

CHILD = {"child", "child_name", "childs_name", "child_full_name", "pupil", "child_s_name"}
CONTACT = {
    "contact",
    "contact_name",
    "collector",
    "collector_name",
    "authorised_person",
    "authorised_collector",
    "person",
    "name_of_contact",
}
RELATIONSHIP = {"relationship", "relation", "relationship_to_child"}
PHONE = {"phone", "mobile", "telephone", "phone_number", "mobile_number", "contact_phone", "tel"}
NOTE = {"password", "collection_password", "note", "notes", "note_for_staff"}


def _key(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", header.strip().lower().replace("'", "")).strip("_")


@dataclass(slots=True)
class ContactRow:
    line: int
    child: Child
    name: str
    relationship: str
    phone: str
    note: str | None


@dataclass(slots=True)
class ImportResult:
    added: list[Authorisation]
    skipped: int


async def _children_by_name(session: AsyncSession, nursery_id: object) -> dict[str, list[Child]]:
    rows = (
        await session.scalars(
            select(Child).where(Child.nursery_id == nursery_id, Child.active.is_(True))
        )
    ).all()
    found: dict[str, list[Child]] = defaultdict(list)
    for child in rows:
        found[names.normalised(child.full_name)].append(child)
    return found


async def _parse(session: AsyncSession, admin: User, text: str) -> list[ContactRow]:
    if len(text.encode()) > MAX_BYTES:
        raise CollectionError("That file is too large.")
    text = text.lstrip("﻿")
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(
            text[:4096], delimiters=",;\t"
        )
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    header = next(reader, None)
    if not header:
        raise CollectionError("The file is empty.")
    keys = [_key(h) for h in header]

    def column(options: set[str]) -> int | None:
        return next((i for i, k in enumerate(keys) if k in options), None)

    cols = {
        "child": column(CHILD),
        "contact": column(CONTACT),
        "relationship": column(RELATIONSHIP),
        "phone": column(PHONE),
        "note": column(NOTE),
    }
    missing = [
        label
        for label, key in (
            ("Child", "child"),
            ("Contact name", "contact"),
            ("Relationship", "relationship"),
            ("Phone", "phone"),
        )
        if cols[key] is None
    ]
    if missing:
        plural = "s" if len(missing) > 1 else ""
        raise CollectionError(f"Missing column{plural}: {', '.join(missing)}.")

    children = await _children_by_name(session, admin.nursery_id)
    rows: list[ContactRow] = []
    problems: list[str] = []
    for line, cells in enumerate(reader, start=2):
        if not any(c.strip() for c in cells):
            continue

        def cell(key: str, cells: list[str] = cells) -> str:
            index = cols[key]
            raw = cells[index] if index is not None and index < len(cells) else ""
            return " ".join(raw.split())

        child_name, name = cell("child"), cell("contact")
        matches = children.get(names.normalised(child_name), [])
        if not matches:
            problems.append(f"line {line}: no child here called '{child_name[:60]}'")
            continue
        if len(matches) > 1:
            problems.append(f"line {line}: two children are called '{child_name[:60]}'")
            continue
        if len(names.words(name)) < 2:
            problems.append(f"line {line}: give the contact's full name")
            continue
        phone = cell("phone")
        if len("".join(ch for ch in phone if ch.isdigit())) < 7:
            problems.append(f"line {line}: no phone number for {name[:60]}")
            continue
        rows.append(
            ContactRow(
                line=line,
                child=matches[0],
                name=name[:200],
                relationship=(cell("relationship") or "Other")[:60],
                phone=phone[:40],
                note=cell("note")[:300] or None,
            )
        )
        if len(rows) > MAX_ROWS:
            raise CollectionError(f"More than {MAX_ROWS} contacts in one file.")
    for row in rows:
        if await restriction_for(session, row.child.id, row.name) is not None:
            problems.append(
                f"line {row.line}: {row.name} is on {row.child.full_name}'s never-release list"
            )
    if problems:
        shown = "; ".join(problems[:5])
        more = f" and {len(problems) - 5} more" if len(problems) > 5 else ""
        raise CollectionError(f"Nothing was imported. Fix these and try again: {shown}{more}.")
    return rows


async def _current(session: AsyncSession, child: Child) -> list[Authorisation]:
    return list(
        (
            await session.scalars(
                select(Authorisation).where(
                    Authorisation.child_id == child.id,
                    Authorisation.revoked_at.is_(None),
                    Authorisation.used_at.is_(None),
                )
            )
        ).all()
    )


async def import_contacts(session: AsyncSession, admin: User, text: str) -> ImportResult:
    """Add every contact in a CSV, or none of them.

    A contact the child already has as a current collector, by any spelling
    of the same name, is skipped rather than added twice.
    """
    rows = await _parse(session, admin, text)
    added: list[Authorisation] = []
    skipped = 0
    current: dict[object, list[Authorisation]] = {}
    for row in rows:
        if row.child.id not in current:
            current[row.child.id] = await _current(session, row.child)
        existing = current[row.child.id]
        if any(names.same_person(a.collector_name, row.name) for a in existing):
            skipped += 1
            continue
        if len(existing) >= MAX_ACTIVE_PER_CHILD:
            raise CollectionError(
                f"Nothing was imported: line {row.line} would give {row.child.full_name} "
                f"more than {MAX_ACTIVE_PER_CHILD} collectors."
            )
        auth = await add_contact(
            session,
            admin,
            row.child.id,
            NewAuthorisation(
                collector_name=row.name,
                collector_relationship=row.relationship,
                collector_phone=row.phone,
                kind=CollectorKind.REGULAR,
                note_for_staff=row.note,
            ),
        )
        existing.append(auth)
        added.append(auth)
    await audit(
        session,
        nursery_id=admin.nursery_id,
        actor=admin,
        action="contacts.imported",
        detail=f"{len(added)} added, {skipped} already there",
    )
    return ImportResult(added=added, skipped=skipped)


async def tell_parents(session: AsyncSession, nursery: Nursery, added: list[Authorisation]) -> None:
    """One email to each parent, listing the contacts added for their children."""
    if not added:
        return
    by_child: dict[object, list[Authorisation]] = defaultdict(list)
    for auth in added:
        by_child[auth.child_id].append(auth)
    links = (
        await session.execute(
            select(ParentLink, User, Child)
            .join(User, User.id == ParentLink.parent_id)
            .join(Child, Child.id == ParentLink.child_id)
            .where(ParentLink.child_id.in_(list(by_child)), User.active.is_(True))
        )
    ).all()
    lines_for: dict[str, list[str]] = defaultdict(list)
    for _link, parent, child in links:
        for auth in by_child[child.id]:
            lines_for[parent.email].append(
                f"- {auth.collector_name} ({auth.collector_relationship}) may collect "
                f"{child.full_name}"
            )
    for email, lines in lines_for.items():
        await send(
            email,
            f"{nursery.name} has added collection contacts",
            f"{nursery.name} has added these people from your registration form as "
            "people who may collect your child:\n\n"
            + "\n".join(lines)
            + "\n\nIf any of them should not collect, remove them in the parent portal "
            "or tell the nursery today.",
        )


async def add_one(
    session: AsyncSession, admin: User, child_id: uuid.UUID, data: NewAuthorisation
) -> Authorisation:
    child = await session.scalar(
        select(Child).where(Child.id == child_id, Child.nursery_id == admin.nursery_id)
    )
    if child is not None and any(
        names.same_person(a.collector_name, data.collector_name)
        for a in await _current(session, child)
    ):
        raise CollectionError(
            f"{data.collector_name} is already a collector for {child.full_name}."
        )
    auth = await add_contact(session, admin, child_id, data)
    await tell_parents(session, await nursery_of(session, admin), [auth])
    return auth
