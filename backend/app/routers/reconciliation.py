"""Reconciling the door record with the nursery's sign-out register."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from app import collection, reconcile
from app.deps import AdminUser, SessionDep
from app.models import SignOutImport, User
from app.routers.admin import _cell
from app.schemas import (
    ReconciliationLineOut,
    ReconciliationOut,
    SignOutImportIn,
    SignOutImportOut,
)

router = APIRouter(prefix="/admin", tags=["reconciliation"])

FLAG_WORDS: dict[str, str] = {
    reconcile.Flag.NO_HANDOVER: "Signed out, but not released at the door",
    reconcile.Flag.NO_SIGN_OUT: "Released at the door, but not signed out",
    reconcile.Flag.COLLECTOR_MISMATCH: "Register names a different collector",
    reconcile.Flag.TIME_GAP: "Sign-out and release more than 15 minutes apart",
    reconcile.Flag.UNKNOWN_CHILD: "Child in the register not found here",
    reconcile.Flag.SIGNED_OUT_TWICE: "Signed out more than once",
}


async def _import_out(
    session: SessionDep, record: SignOutImport, imported_by: str | None = None
) -> SignOutImportOut:
    if imported_by is None:
        who = await session.get(User, record.imported_by_id)
        imported_by = who.full_name if who else None
    return SignOutImportOut(
        id=record.id,
        day=record.day,
        source=record.source,
        rows=record.rows,
        imported_at=record.imported_at,
        imported_by_name=imported_by,
    )


@router.post(
    "/sign-outs/import", response_model=SignOutImportOut, status_code=status.HTTP_201_CREATED
)
async def import_sign_outs(
    body: SignOutImportIn, admin: AdminUser, session: SessionDep
) -> SignOutImportOut:
    """One day's sign-outs, as CSV exported from the nursery's own system.

    Needs a column for the child's name (or first name and surname) and one for
    the time signed out; a 'Collected by' column is compared with the door too.
    """
    record = await reconcile.import_register(session, admin, body.day, body.csv, body.source)
    return await _import_out(session, record, admin.full_name)


@router.get("/reconciliation", response_model=ReconciliationOut)
async def reconciliation(
    admin: AdminUser, session: SessionDep, day: date | None = None
) -> ReconciliationOut:
    if day is None:
        nursery = await collection.nursery_of(session, admin)
        day = collection.local_date(nursery, datetime.now(UTC))
    result = await reconcile.reconcile(session, admin, day)
    lines = [
        ReconciliationLineOut(
            child_name=line.child_name,
            child_id=line.child_id,
            signed_out_at=line.signed_out_at,
            register_collected_by=line.register_collected_by,
            released_at=line.released_at,
            collector_name=line.collector_name,
            collector_relationship=line.collector_relationship,
            staff_name=line.staff_name,
            id_check_method=line.id_check_method,
            refusals=line.refusals,
            flags=[flag.value for flag in line.flags],
        )
        for line in result.lines
    ]
    flagged = sum(1 for line in lines if line.flags)
    return ReconciliationOut(
        day=result.day,
        register_import=(
            await _import_out(session, result.register, result.imported_by)
            if result.register
            else None
        ),
        lines=lines,
        flagged=flagged,
        matched=len(lines) - flagged if result.register else 0,
    )


@router.get("/reconciliation.csv")
async def reconciliation_csv(
    admin: AdminUser, session: SessionDep, day: date | None = None
) -> StreamingResponse:
    out = await reconciliation(admin, session, day)
    nursery = await collection.nursery_of(session, admin)

    def clock(moment: datetime | None) -> str:
        return f"{collection.local_time(nursery, moment):%H:%M}" if moment else ""

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "day",
            "child",
            "signed_out",
            "register_collected_by",
            "released_at_door",
            "collector",
            "relationship",
            "checked_by",
            "id_check",
            "refusals",
            "flags",
        ]
    )
    for line in out.lines:
        writer.writerow(
            [
                out.day.isoformat(),
                _cell(line.child_name),
                clock(line.signed_out_at),
                _cell(line.register_collected_by or ""),
                clock(line.released_at),
                _cell(line.collector_name or ""),
                _cell(line.collector_relationship or ""),
                _cell(line.staff_name or ""),
                line.id_check_method.value if line.id_check_method else "",
                _cell(" | ".join(line.refusals)),
                "; ".join(FLAG_WORDS.get(f, f) for f in line.flags) or "OK",
            ]
        )
    await collection.audit(
        session,
        nursery_id=admin.nursery_id,
        actor=admin,
        action="reconciliation.exported",
        detail=out.day.strftime("%d/%m/%Y"),
    )
    name = f"reconciliation-{out.day.isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
