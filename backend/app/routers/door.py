"""The door: staff check a collector and record the handover."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app import collection, geofence, photos, register
from app.deps import SessionDep, StaffUser
from app.models import Authorisation, CheckResult, Child, DoorCheck, Nursery, User
from app.schemas import (
    AbsenceOut,
    ArrivalIn,
    CheckOut,
    ChildOut,
    CodeCheckIn,
    DecisionIn,
    GeofenceOut,
    HandoverOut,
    PassCheckIn,
    PositionIn,
    RegisterChildOut,
    RegisterOut,
    RegisterSyncIn,
    RegisterSyncOut,
    RegisterSyncResult,
    RestrictionAtDoor,
    StaffAbsenceIn,
)

router = APIRouter(prefix="/door", tags=["door"])

MESSAGES: dict[CheckResult, str] = {
    CheckResult.VALID: "Authorised. Check the collector's ID, then release or refuse.",
    CheckResult.UNREADABLE: "That is not a collector pass. Do not release the child.",
    CheckResult.WRONG_NURSERY: "This pass was not issued by this nursery. Do not release.",
    CheckResult.UNKNOWN: "No such collector. Do not release the child.",
    CheckResult.RESTRICTED: (
        "This person is on the child's never-release list. Do not release the child. "
        "Keep the child inside and tell the manager now."
    ),
    CheckResult.REVOKED: "The parent has removed this collector. Do not release the child.",
    CheckResult.REISSUED: "This is an old pass that has been replaced. Do not release.",
    CheckResult.NOT_YET_VALID: "This collector is not authorised yet. Do not release.",
    CheckResult.EXPIRED: "This authorisation has ended. Do not release the child.",
    CheckResult.ALREADY_USED: "This one-off pass has already been used. Do not release.",
    CheckResult.ALREADY_COLLECTED: "This child has already been collected today. Do not release.",
    CheckResult.WRONG_CODE: "That code does not match any collector for this child.",
    CheckResult.LOCKED: "Too many wrong codes for this child. Call the parent.",
    CheckResult.OUTSIDE_GEOFENCE: (
        "This phone is outside the nursery's geofence. Checks can only be made on site."
    ),
    CheckResult.NO_LOCATION: (
        "The nursery has a geofence, and this phone did not share its location. "
        "Allow location for this site and try again."
    ),
}


def _position(body: PositionIn | None) -> geofence.Position | None:
    if body is None or not geofence.valid_coordinates(body.latitude, body.longitude):
        return None
    return geofence.Position(body.latitude, body.longitude, body.accuracy_m)


async def _out(session: SessionDep, check: DoorCheck) -> CheckOut:
    out = CheckOut(
        check_id=check.id,
        result=check.result,
        method=check.method,
        message=MESSAGES[check.result],
        can_release=check.result is CheckResult.VALID,
    )
    child = await session.get(Child, check.child_id) if check.child_id else None
    if child is not None:
        out.child_id = child.id
        out.child_name = child.full_name
        out.room = child.room
        out.restrictions = [
            RestrictionAtDoor(person_name=r.person_name, reason=r.reason)
            for r in await collection.restrictions_for_child(session, child.id)
        ]
        if check.result is CheckResult.ALREADY_COLLECTED:
            # Say when and to whom, so staff can tell the person at the door.
            nursery = await session.get(Nursery, child.nursery_id)
            assert nursery is not None
            earlier = await collection.released_today(session, nursery, child.id, check.checked_at)
            if earlier is not None:
                when = collection.local_time(nursery, earlier.occurred_at)
                out.message = (
                    f"{child.full_name} was already collected at "
                    f"{when:%H:%M} by {earlier.collector_name} "
                    f"({earlier.collector_relationship}). Do not release."
                )
    auth = (
        await session.get(Authorisation, check.authorisation_id) if check.authorisation_id else None
    )
    if auth is not None:
        out.collector_name = auth.collector_name
        if check.result is CheckResult.VALID:
            parent = await session.get(User, auth.authorised_by_id)
            out.collector_relationship = auth.collector_relationship
            out.collector_phone = auth.collector_phone
            out.note_for_staff = auth.note_for_staff
            out.authorised_by_name = parent.full_name if parent else None
            out.kind = auth.kind
            out.valid_until = auth.valid_until
            out.has_photo = await photos.has_photo(session, auth.id)
    return out


@router.get("/children", response_model=list[ChildOut])
async def children(staff: StaffUser, session: SessionDep) -> list[Child]:
    rows = await session.scalars(
        select(Child)
        .where(Child.nursery_id == staff.nursery_id, Child.active.is_(True))
        .order_by(Child.full_name)
    )
    return list(rows.all())


@router.get("/geofence", response_model=GeofenceOut)
async def door_geofence(staff: StaffUser, session: SessionDep) -> GeofenceOut:
    """Whether the door screen must send its position with each check."""
    nursery = await collection.nursery_of(session, staff)
    fence = collection.fence_of(nursery)
    return GeofenceOut(enabled=fence is not None)


@router.post("/check/pass", response_model=CheckOut)
async def check_pass(body: PassCheckIn, staff: StaffUser, session: SessionDep) -> CheckOut:
    check = await collection.check_pass(session, staff, body.token, _position(body.position))
    return await _out(session, check)


@router.post("/check/code", response_model=CheckOut)
async def check_code(body: CodeCheckIn, staff: StaffUser, session: SessionDep) -> CheckOut:
    check = await collection.check_code(
        session, staff, body.child_id, body.code, _position(body.position)
    )
    return await _out(session, check)


@router.post("/checks/{check_id}/decision", response_model=HandoverOut)
async def decide(
    check_id: uuid.UUID, body: DecisionIn, staff: StaffUser, session: SessionDep
) -> HandoverOut:
    handover = await collection.decide(
        session,
        staff,
        check_id,
        release=body.release,
        reason=body.reason,
        id_check_method=body.id_check_method,
    )
    return HandoverOut.model_validate(handover)


@router.get("/checks/{check_id}/photo")
async def check_photo(check_id: uuid.UUID, staff: StaffUser, session: SessionDep) -> Response:
    """The collector's photo, for a check that came back valid a moment ago.

    Only then: the door has no reason to browse collectors' photos, and a
    check older than the decision window cannot lead to a handover anyway.
    """
    check = await session.scalar(
        select(DoorCheck).where(DoorCheck.id == check_id, DoorCheck.nursery_id == staff.nursery_id)
    )
    if (
        check is None
        or check.result is not CheckResult.VALID
        or check.authorisation_id is None
        or datetime.now(UTC) - check.checked_at > collection.DECISION_WINDOW
    ):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    photo = await photos.get(session, check.authorisation_id)
    if photo is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return Response(content=photo.data, media_type=photo.content_type)


# The arrival register.


def _register_row(row: register.RegisterRow) -> RegisterChildOut:
    return RegisterChildOut(
        child_id=row.child.id,
        full_name=row.child.full_name,
        room=row.child.room,
        expected=row.expected,
        arrived_at=row.arrival.arrived_at if row.arrival else None,
        arrived_offline=bool(row.arrival and row.arrival.recorded_offline),
        absence_reason=row.absence.reason if row.absence else None,
        absence_note=row.absence.note if row.absence else None,
        collected_at=row.collected.occurred_at if row.collected else None,
        collected_by=row.collected.collector_name if row.collected else None,
    )


@router.get("/register", response_model=RegisterOut)
async def today_register(staff: StaffUser, session: SessionDep) -> RegisterOut:
    nursery = await collection.nursery_of(session, staff)
    day = collection.local_date(nursery, datetime.now(UTC))
    rows = await register.register_for(session, nursery, day)
    return RegisterOut(
        day=day,
        children=[_register_row(r) for r in rows],
        arrival_alert_at=nursery.arrival_alert_at,
    )


async def _row_for(session: SessionDep, staff: User, child_id: uuid.UUID) -> RegisterChildOut:
    nursery = await collection.nursery_of(session, staff)
    day = collection.local_date(nursery, datetime.now(UTC))
    for row in await register.register_for(session, nursery, day):
        if row.child.id == child_id:
            return _register_row(row)
    raise collection.CollectionError("No such child at this nursery.", status=404)


@router.post("/register/arrivals", response_model=RegisterChildOut)
async def mark_in(body: ArrivalIn, staff: StaffUser, session: SessionDep) -> RegisterChildOut:
    await register.mark_arrival(
        session, staff, body.child_id, occurred_at=body.occurred_at, client_id=body.client_id
    )
    return await _row_for(session, staff, body.child_id)


@router.delete("/register/arrivals/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
async def undo_mark(child_id: uuid.UUID, staff: StaffUser, session: SessionDep) -> None:
    await register.undo_arrival(session, staff, child_id)


@router.post("/register/sync", response_model=RegisterSyncOut)
async def sync_marks(
    body: RegisterSyncIn, staff: StaffUser, session: SessionDep
) -> RegisterSyncOut:
    """Marks made on a phone without signal, sent when it reconnects.

    Each is recorded at the time it was made, once however often it is sent,
    and a refusal of one never stops the rest being recorded.
    """
    results: list[RegisterSyncResult] = []
    for mark in body.marks:
        try:
            marked = await register.mark_arrival(
                session,
                staff,
                mark.child_id,
                occurred_at=mark.occurred_at,
                client_id=mark.client_id,
                offline=True,
            )
        except collection.CollectionError as refused:
            results.append(
                RegisterSyncResult(
                    client_id=mark.client_id,
                    child_id=mark.child_id,
                    status="rejected",
                    message=str(refused),
                )
            )
            continue
        results.append(
            RegisterSyncResult(
                client_id=mark.client_id, child_id=mark.child_id, status=marked.status
            )
        )
    if results:
        await collection.audit(
            session,
            nursery_id=staff.nursery_id,
            actor=staff,
            action="register.synced",
            detail=f"{sum(r.status == 'recorded' for r in results)} of {len(results)} "
            "offline marks recorded",
        )
    return RegisterSyncOut(results=results)


@router.post("/register/absences", response_model=AbsenceOut, status_code=status.HTTP_201_CREATED)
async def phoned_in_absence(
    body: StaffAbsenceIn, staff: StaffUser, session: SessionDep
) -> AbsenceOut:
    absence = await register.report_absence(
        session, staff, body.child_id, body.day, body.reason, body.note
    )
    return AbsenceOut.model_validate(absence)
