"""The nursery's own administration: people, children, and the record."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import collection, geofence
from app.deps import AdminUser, SessionDep
from app.models import (
    Authorisation,
    CheckResult,
    Child,
    DoorCheck,
    Handover,
    HandoverOutcome,
    ParentLink,
    User,
)
from app.routers.parent import authorisation_out
from app.schemas import (
    AuthorisationOut,
    ChildIn,
    ChildOut,
    DoorCheckOut,
    GeofenceIn,
    GeofenceOut,
    HandoverOut,
    LinkIn,
    LinkOut,
    PersonIn,
    PersonOut,
    TodayOut,
)
from app.security import hash_password, password_problem

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/today", response_model=TodayOut)
async def today(admin: AdminUser, session: SessionDep) -> TodayOut:
    nursery = await collection.nursery_of(session, admin)
    start, end = collection.day_bounds(nursery, collection.local_date(nursery, datetime.now(UTC)))

    async def handovers(outcome: HandoverOutcome) -> int:
        count = await session.scalar(
            select(func.count())
            .select_from(Handover)
            .where(
                Handover.nursery_id == admin.nursery_id,
                Handover.outcome == outcome,
                Handover.occurred_at.between(start, end),
            )
        )
        return int(count or 0)

    exceptions = await session.scalar(
        select(func.count())
        .select_from(DoorCheck)
        .where(
            DoorCheck.nursery_id == admin.nursery_id,
            DoorCheck.result != CheckResult.VALID,
            DoorCheck.checked_at.between(start, end),
        )
    )
    active = await session.scalar(
        select(func.count())
        .select_from(Authorisation)
        .where(
            Authorisation.nursery_id == admin.nursery_id,
            Authorisation.revoked_at.is_(None),
            Authorisation.used_at.is_(None),
        )
    )
    return TodayOut(
        released=await handovers(HandoverOutcome.RELEASED),
        refused=await handovers(HandoverOutcome.REFUSED),
        exceptions=int(exceptions or 0),
        active_collectors=int(active or 0),
    )


def _range(start: date | None, end: date | None) -> tuple[datetime, datetime]:
    end_day = end or datetime.now(UTC).date()
    start_day = start or end_day - timedelta(days=30)
    if start_day > end_day:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The start is after the end.")
    return (
        datetime.combine(start_day, datetime.min.time(), tzinfo=UTC),
        datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=UTC),
    )


@router.get("/handovers", response_model=list[HandoverOut])
async def handovers(
    admin: AdminUser,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
    child_id: uuid.UUID | None = None,
) -> list[Handover]:
    since, until = _range(start, end)
    query = select(Handover).where(
        Handover.nursery_id == admin.nursery_id,
        Handover.occurred_at >= since,
        Handover.occurred_at < until,
    )
    if child_id is not None:
        query = query.where(Handover.child_id == child_id)
    rows = await session.scalars(query.order_by(Handover.occurred_at.desc()).limit(1000))
    return list(rows.all())


@router.get("/handovers.csv")
async def handovers_csv(
    admin: AdminUser,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
) -> StreamingResponse:
    rows = await handovers(admin, session, start, end)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "occurred_at_utc",
            "child",
            "outcome",
            "collector",
            "relationship",
            "authorised_by",
            "checked_by",
            "refusal_reason",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.occurred_at.isoformat(),
                _cell(row.child_name),
                row.outcome.value,
                _cell(row.collector_name),
                _cell(row.collector_relationship),
                _cell(row.authorised_by_name),
                _cell(row.staff_name),
                _cell(row.refusal_reason or ""),
            ]
        )
    await collection.audit(
        session, nursery_id=admin.nursery_id, actor=admin, action="handovers.exported"
    )
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="handovers.csv"'},
    )


def _cell(value: str) -> str:
    # A cell starting with = + - or @ is run as a formula by spreadsheet apps.
    return "'" + value if value[:1] in {"=", "+", "-", "@"} else value


@router.get("/checks", response_model=list[DoorCheckOut])
async def checks(
    admin: AdminUser,
    session: SessionDep,
    exceptions_only: bool = Query(default=True),
    start: date | None = None,
    end: date | None = None,
) -> list[DoorCheckOut]:
    since, until = _range(start, end)
    query = select(DoorCheck).where(
        DoorCheck.nursery_id == admin.nursery_id,
        DoorCheck.checked_at >= since,
        DoorCheck.checked_at < until,
    )
    if exceptions_only:
        query = query.where(DoorCheck.result != CheckResult.VALID)
    rows = (await session.scalars(query.order_by(DoorCheck.checked_at.desc()).limit(1000))).all()
    out: list[DoorCheckOut] = []
    for check in rows:
        child = await session.get(Child, check.child_id) if check.child_id else None
        auth = (
            await session.get(Authorisation, check.authorisation_id)
            if check.authorisation_id
            else None
        )
        staff = await session.get(User, check.checked_by_id)
        out.append(
            DoorCheckOut(
                id=check.id,
                checked_at=check.checked_at,
                method=check.method,
                result=check.result,
                child_name=child.full_name if child else None,
                collector_name=auth.collector_name if auth else None,
                staff_name=staff.full_name if staff else "Unknown",
                distance_m=check.distance_m,
            )
        )
    return out


def _fence_out(fence: geofence.Fence | None) -> GeofenceOut:
    if fence is None:
        return GeofenceOut(enabled=False)
    return GeofenceOut(
        enabled=True,
        latitude=fence.latitude,
        longitude=fence.longitude,
        radius_m=fence.radius_m,
    )


@router.get("/geofence", response_model=GeofenceOut)
async def get_geofence(admin: AdminUser, session: SessionDep) -> GeofenceOut:
    return _fence_out(collection.fence_of(await collection.nursery_of(session, admin)))


@router.put("/geofence", response_model=GeofenceOut)
async def set_geofence(body: GeofenceIn, admin: AdminUser, session: SessionDep) -> GeofenceOut:
    """Only accept door checks from phones within this circle."""
    if not geofence.valid_coordinates(body.latitude, body.longitude):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Those are not real coordinates.")
    nursery = await collection.nursery_of(session, admin)
    nursery.geofence_latitude = body.latitude
    nursery.geofence_longitude = body.longitude
    nursery.geofence_radius_m = body.radius_m
    await collection.audit(
        session,
        nursery_id=admin.nursery_id,
        actor=admin,
        action="geofence.set",
        detail=f"{body.latitude:.5f},{body.longitude:.5f} r={body.radius_m}m",
    )
    return _fence_out(collection.fence_of(nursery))


@router.delete("/geofence", response_model=GeofenceOut)
async def clear_geofence(admin: AdminUser, session: SessionDep) -> GeofenceOut:
    nursery = await collection.nursery_of(session, admin)
    nursery.geofence_latitude = None
    nursery.geofence_longitude = None
    nursery.geofence_radius_m = None
    await collection.audit(
        session, nursery_id=admin.nursery_id, actor=admin, action="geofence.cleared"
    )
    return _fence_out(None)


@router.get("/children", response_model=list[ChildOut])
async def list_children(admin: AdminUser, session: SessionDep) -> list[Child]:
    rows = await session.scalars(
        select(Child).where(Child.nursery_id == admin.nursery_id).order_by(Child.full_name)
    )
    return list(rows.all())


@router.post("/children", response_model=ChildOut, status_code=status.HTTP_201_CREATED)
async def add_child(body: ChildIn, admin: AdminUser, session: SessionDep) -> Child:
    child = Child(nursery_id=admin.nursery_id, full_name=body.full_name.strip(), room=body.room)
    session.add(child)
    await session.flush()
    await collection.audit(
        session,
        nursery_id=admin.nursery_id,
        actor=admin,
        action="child.added",
        subject_id=child.id,
    )
    return child


@router.post("/children/{child_id}/leave", response_model=ChildOut)
async def child_leaves(child_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> Child:
    """A child leaving: every collector for them stops working at once."""
    child = await collection.child_in_nursery(session, admin, child_id)
    child.active = False
    auths = await session.scalars(
        select(Authorisation).where(
            Authorisation.child_id == child.id, Authorisation.revoked_at.is_(None)
        )
    )
    for auth in auths.all():
        await collection.revoke(session, admin, auth)
    await collection.audit(
        session, nursery_id=admin.nursery_id, actor=admin, action="child.left", subject_id=child.id
    )
    return child


@router.get("/children/{child_id}/collectors", response_model=list[AuthorisationOut])
async def child_collectors(
    child_id: uuid.UUID, admin: AdminUser, session: SessionDep
) -> list[AuthorisationOut]:
    child = await collection.child_in_nursery(session, admin, child_id)
    rows = await session.scalars(
        select(Authorisation)
        .where(Authorisation.child_id == child.id)
        .order_by(Authorisation.created_at.desc())
    )
    now = datetime.now(UTC)
    return [await authorisation_out(session, auth, now) for auth in rows.all()]


@router.post("/collectors/{authorisation_id}/revoke", response_model=AuthorisationOut)
async def admin_revoke(
    authorisation_id: uuid.UUID, admin: AdminUser, session: SessionDep
) -> AuthorisationOut:
    """For a court order, a safeguarding concern or a parent who rings in."""
    auth = await session.scalar(
        select(Authorisation).where(
            Authorisation.id == authorisation_id, Authorisation.nursery_id == admin.nursery_id
        )
    )
    if auth is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such collector.")
    await collection.revoke(session, admin, auth)
    return await authorisation_out(session, auth, datetime.now(UTC))


@router.get("/people", response_model=list[PersonOut])
async def people(admin: AdminUser, session: SessionDep) -> list[User]:
    rows = await session.scalars(
        select(User).where(User.nursery_id == admin.nursery_id).order_by(User.full_name)
    )
    return list(rows.all())


@router.post("/people", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def add_person(body: PersonIn, admin: AdminUser, session: SessionDep) -> User:
    problem = password_problem(body.password)
    if problem:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    existing = await session.scalar(
        select(User).where(func.lower(User.email) == body.email.lower())
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Someone already uses that email address.")
    user = User(
        nursery_id=admin.nursery_id,
        email=body.email.lower(),
        full_name=body.full_name.strip(),
        phone=body.phone,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "That email is already in use.") from exc
    await collection.audit(
        session,
        nursery_id=admin.nursery_id,
        actor=admin,
        action="person.added",
        subject_id=user.id,
        detail=body.role.value,
    )
    return user


@router.post("/people/{user_id}/deactivate", response_model=PersonOut)
async def deactivate(user_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> User:
    user = await session.scalar(
        select(User).where(User.id == user_id, User.nursery_id == admin.nursery_id)
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such person.")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot switch off your own account.")
    user.active = False
    await collection.audit(
        session,
        nursery_id=admin.nursery_id,
        actor=admin,
        action="person.deactivated",
        subject_id=user.id,
    )
    return user


@router.get("/links", response_model=list[LinkOut])
async def links(admin: AdminUser, session: SessionDep) -> list[LinkOut]:
    rows = (
        await session.execute(
            select(ParentLink, User, Child)
            .join(User, User.id == ParentLink.parent_id)
            .join(Child, Child.id == ParentLink.child_id)
            .where(ParentLink.nursery_id == admin.nursery_id)
            .order_by(Child.full_name)
        )
    ).all()
    return [
        LinkOut(
            parent_id=user.id,
            parent_name=user.full_name,
            child_id=child.id,
            child_name=child.full_name,
            relationship_label=link.relationship_label,
        )
        for link, user, child in rows
    ]


@router.post("/links", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
async def link(body: LinkIn, admin: AdminUser, session: SessionDep) -> LinkOut:
    parent = await session.scalar(
        select(User).where(User.id == body.parent_id, User.nursery_id == admin.nursery_id)
    )
    if parent is None or parent.role.value != "parent":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such parent at this nursery.")
    child = await collection.child_in_nursery(session, admin, body.child_id)
    existing = await session.scalar(
        select(ParentLink).where(ParentLink.parent_id == parent.id, ParentLink.child_id == child.id)
    )
    if existing is None:
        session.add(
            ParentLink(
                nursery_id=admin.nursery_id,
                parent_id=parent.id,
                child_id=child.id,
                relationship_label=body.relationship_label,
            )
        )
        await collection.audit(
            session,
            nursery_id=admin.nursery_id,
            actor=admin,
            action="parent.linked",
            subject_id=child.id,
            detail=parent.full_name,
        )
    return LinkOut(
        parent_id=parent.id,
        parent_name=parent.full_name,
        child_id=child.id,
        child_name=child.full_name,
        relationship_label=body.relationship_label,
    )
