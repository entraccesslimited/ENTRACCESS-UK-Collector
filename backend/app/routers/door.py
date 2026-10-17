"""The door: staff check a collector and record the handover."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app import collection, geofence
from app.deps import SessionDep, StaffUser
from app.models import Authorisation, CheckResult, Child, DoorCheck, Nursery, User
from app.schemas import (
    CheckOut,
    ChildOut,
    CodeCheckIn,
    DecisionIn,
    GeofenceOut,
    HandoverOut,
    PassCheckIn,
    PositionIn,
)

router = APIRouter(prefix="/door", tags=["door"])

MESSAGES: dict[CheckResult, str] = {
    CheckResult.VALID: "Authorised. Check the collector's ID, then release or refuse.",
    CheckResult.UNREADABLE: "That is not a collector pass. Do not release the child.",
    CheckResult.WRONG_NURSERY: "This pass was not issued by this nursery. Do not release.",
    CheckResult.UNKNOWN: "No such collector. Do not release the child.",
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
        id_checked=body.id_checked,
    )
    return HandoverOut.model_validate(handover)
