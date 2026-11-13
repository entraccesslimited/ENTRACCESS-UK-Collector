"""The KPI summary and the evidence pack."""

from __future__ import annotations

import csv
import dataclasses
import io
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app import collection, reports
from app.deps import AdminUser, SessionDep
from app.models import User
from app.routers.admin import _cell
from app.routers.reconciliation import FLAG_WORDS
from app.schemas import (
    EvidenceCollectorOut,
    EvidenceEventOut,
    EvidenceFlagOut,
    EvidenceOut,
    EvidenceRestrictionOut,
    KpisOut,
)

router = APIRouter(prefix="/admin", tags=["reports"])

KPI_ROWS: list[tuple[str, str]] = [
    ("releases", "Children released at the door"),
    ("refusals", "Collections refused by staff"),
    ("blocked_checks", "Checks refused by the app"),
    ("collectors_added_by_parents", "Collectors added by parents"),
    ("one_off_collectors", "  of which one-off"),
    ("contacts_added_by_nursery", "Contacts added by the nursery"),
    ("collectors_removed", "Collectors removed"),
    ("passes_shared", "Passes sent to collectors"),
    ("restrictions_added", "Never-release restrictions added"),
    ("restrictions_in_force", "Never-release restrictions in force at the end"),
    ("days_with_releases", "Days with releases"),
    ("registers_imported", "Days with the sign-out register imported"),
    ("days_without_register", "Days with releases but no register imported"),
]


async def _period(
    session: SessionDep, admin: User, start: date | None, end: date | None
) -> tuple[date, date]:
    nursery = await collection.nursery_of(session, admin)
    return reports.period(collection.local_date(nursery, datetime.now(UTC)), start, end)


def _kpis_out(k: reports.Kpis) -> KpisOut:
    return KpisOut(**dataclasses.asdict(k))


@router.get("/kpis", response_model=KpisOut)
async def kpis(
    admin: AdminUser,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
    child_id: uuid.UUID | None = None,
) -> KpisOut:
    first, last = await _period(session, admin, start, end)
    return _kpis_out(await reports.kpis(session, admin, first, last, child_id))


def _csv(name: str, rows: list[list[str]]) -> StreamingResponse:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/kpis.csv")
async def kpis_csv(
    admin: AdminUser,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
) -> StreamingResponse:
    first, last = await _period(session, admin, start, end)
    k = await reports.kpis(session, admin, first, last)
    values = dataclasses.asdict(k)
    rows = [["measure", "value"], ["period", f"{first.isoformat()} to {last.isoformat()}"]]
    rows += [[label.strip(), str(values[key])] for key, label in KPI_ROWS]
    rows += [[f"ID check: {m.replace('_', ' ')}", str(n)] for m, n in k.id_checks.items()]
    rows += [
        [f"Refused by the app: {r.replace('_', ' ')}", str(n)]
        for r, n in k.blocked_by_result.items()
    ]
    rows += [[f"Refusal reason: {_cell(r)}", str(n)] for r, n in k.refusal_reasons]
    rows += [
        [f"Reconciliation: {FLAG_WORDS.get(f, f)}", str(n)]
        for f, n in k.reconciliation_flags.items()
    ]
    await collection.audit(
        session,
        nursery_id=admin.nursery_id,
        actor=admin,
        action="kpis.exported",
        detail=f"{first:%d/%m/%Y} to {last:%d/%m/%Y}",
    )
    return _csv(f"kpis-{first.isoformat()}-to-{last.isoformat()}.csv", rows)


async def _evidence(
    session: SessionDep,
    admin: User,
    start: date | None,
    end: date | None,
    child_id: uuid.UUID | None,
) -> EvidenceOut:
    first, last = await _period(session, admin, start, end)
    pack = await reports.evidence(session, admin, first, last, child_id)
    users = {
        u.id: u.full_name
        for u in (await session.scalars(select(User).where(User.nursery_id == admin.nursery_id)))
    }
    return EvidenceOut(
        nursery_name=pack.nursery_name,
        start=pack.start,
        end=pack.end,
        child_name=pack.child_name,
        generated_at=pack.generated_at,
        generated_by=pack.generated_by,
        kpis=_kpis_out(pack.kpis),
        collectors=[
            EvidenceCollectorOut(
                child_name=pack.collector_names[a.id],
                collector_name=a.collector_name,
                collector_relationship=a.collector_relationship,
                kind=a.kind,
                source=a.source,
                authorised_by_name=users.get(a.authorised_by_id, "Unknown"),
                created_at=a.created_at,
                valid_until=a.valid_until,
                revoked_at=a.revoked_at,
                used_at=a.used_at,
            )
            for a in pack.collectors
        ],
        restrictions=[
            EvidenceRestrictionOut(
                child_name=pack.restriction_children[r.id],
                person_name=r.person_name,
                reason=r.reason,
                reference=r.reference,
                created_at=r.created_at,
                created_by_name=users.get(r.created_by_id, "Unknown"),
                ended_at=r.ended_at,
            )
            for r in pack.restrictions
        ],
        events=[EvidenceEventOut(**dataclasses.asdict(e)) for e in pack.events],
        flagged=[
            EvidenceFlagOut(
                day=f.day,
                child_name=f.line.child_name,
                flags=[x.value for x in f.line.flags],
                signed_out_at=f.line.signed_out_at,
                register_collected_by=f.line.register_collected_by,
                released_at=f.line.released_at,
                collector_name=f.line.collector_name,
            )
            for f in pack.flagged
        ],
        registers=pack.registers,
    )


@router.get("/evidence", response_model=EvidenceOut)
async def evidence(
    admin: AdminUser,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
    child_id: uuid.UUID | None = None,
) -> EvidenceOut:
    """Everything about collections in a period, for one child or all. Logged."""
    out = await _evidence(session, admin, start, end, child_id)
    await collection.audit(
        session,
        nursery_id=admin.nursery_id,
        actor=admin,
        action="evidence.exported",
        subject_id=child_id,
        detail=f"{out.child_name or 'all children'}, {out.start:%d/%m/%Y} to {out.end:%d/%m/%Y}",
    )
    return out


@router.get("/evidence.csv")
async def evidence_csv(
    admin: AdminUser,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
    child_id: uuid.UUID | None = None,
) -> StreamingResponse:
    """The evidence pack's timeline as one CSV: every event, oldest first."""
    out = await evidence(admin, session, start, end, child_id)
    nursery = await collection.nursery_of(session, admin)
    rows = [["at_local", "kind", "child", "detail", "who"]]
    rows += [
        [
            f"{collection.local_time(nursery, e.at):%Y-%m-%d %H:%M}",
            e.kind,
            _cell(e.child),
            _cell(e.detail),
            _cell(e.who),
        ]
        for e in out.events
    ]
    rows += [
        [
            f.day.isoformat(),
            "reconciliation",
            _cell(f.child_name),
            "; ".join(FLAG_WORDS.get(x, x) for x in f.flags),
            "",
        ]
        for f in out.flagged
    ]
    scope = "all" if child_id is None else _slug(out.child_name or "child")
    return _csv(f"evidence-{scope}-{out.start.isoformat()}-to-{out.end.isoformat()}.csv", rows)


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-") or "child"
