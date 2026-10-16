"""The company portal: ENTRACCESS UK running every nursery.

Operators set nurseries up with their first manager, see how each is doing,
and suspend or reactivate them. Every answer here is a count or a setting.
None names a child, a parent or a collector: running the service does not
require reading anybody's family.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentOperator, SessionDep
from app.models import (
    AuditEvent,
    Authorisation,
    CheckResult,
    Child,
    DoorCheck,
    Handover,
    HandoverOutcome,
    Nursery,
    Operator,
    Role,
    User,
)
from app.schemas import CompanyOverview, NewNursery, NurseryRow
from app.security import hash_password, password_problem

router = APIRouter(prefix="/company", tags=["company"])

SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])$")


async def _counts(session: AsyncSession, query: object) -> dict[uuid.UUID, int]:
    rows = (await session.execute(query)).all()  # type: ignore[call-overload]
    return {row[0]: int(row[1]) for row in rows}


@router.get("/nurseries", response_model=list[NurseryRow])
async def nurseries(_operator: CurrentOperator, session: SessionDep) -> list[NurseryRow]:
    since = datetime.now(UTC) - timedelta(days=30)
    children = await _counts(
        session,
        select(Child.nursery_id, func.count())
        .where(Child.active.is_(True))
        .group_by(Child.nursery_id),
    )
    people = (
        await session.execute(
            select(User.nursery_id, User.role, func.count())
            .where(User.active.is_(True))
            .group_by(User.nursery_id, User.role)
        )
    ).all()
    by_role: dict[tuple[uuid.UUID, Role], int] = {(n, r): int(c) for n, r, c in people}
    collectors = await _counts(
        session,
        select(Authorisation.nursery_id, func.count())
        .where(Authorisation.revoked_at.is_(None), Authorisation.used_at.is_(None))
        .group_by(Authorisation.nursery_id),
    )
    released = await _counts(
        session,
        select(Handover.nursery_id, func.count())
        .where(Handover.occurred_at >= since, Handover.outcome == HandoverOutcome.RELEASED)
        .group_by(Handover.nursery_id),
    )
    exceptions = await _counts(
        session,
        select(DoorCheck.nursery_id, func.count())
        .where(DoorCheck.checked_at >= since, DoorCheck.result != CheckResult.VALID)
        .group_by(DoorCheck.nursery_id),
    )
    rows = (await session.scalars(select(Nursery).order_by(Nursery.name))).all()
    return [
        NurseryRow(
            id=n.id,
            name=n.name,
            slug=n.slug,
            active=n.active,
            created_at=n.created_at,
            geofence_on=n.geofence_latitude is not None,
            children=children.get(n.id, 0),
            parents=by_role.get((n.id, Role.PARENT), 0),
            room_leaders=by_role.get((n.id, Role.STAFF), 0),
            managers=by_role.get((n.id, Role.ADMIN), 0),
            active_collectors=collectors.get(n.id, 0),
            collections_30d=released.get(n.id, 0),
            exceptions_30d=exceptions.get(n.id, 0),
        )
        for n in rows
    ]


@router.get("/overview", response_model=CompanyOverview)
async def overview(operator: CurrentOperator, session: SessionDep) -> CompanyOverview:
    rows = await nurseries(operator, session)
    return CompanyOverview(
        nurseries=len(rows),
        active_nurseries=sum(1 for r in rows if r.active),
        children=sum(r.children for r in rows),
        active_collectors=sum(r.active_collectors for r in rows),
        collections_30d=sum(r.collections_30d for r in rows),
        exceptions_30d=sum(r.exceptions_30d for r in rows),
    )


def _log(
    operator: Operator, nursery: Nursery, action: str, detail: str | None = None
) -> AuditEvent:
    return AuditEvent(
        nursery_id=nursery.id,
        actor_id=None,
        action=action,
        subject_id=nursery.id,
        detail=f"by ENTRACCESS UK operator {operator.email}" + (f": {detail}" if detail else ""),
    )


@router.post("/nurseries", response_model=NurseryRow, status_code=status.HTTP_201_CREATED)
async def add_nursery(
    body: NewNursery, operator: CurrentOperator, session: SessionDep
) -> NurseryRow:
    """Set up a nursery and its first manager, who then adds everyone else."""
    slug = body.slug.strip().lower()
    if not SLUG.match(slug):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The address uses lower-case letters, numbers and hyphens, 3 to 50 long.",
        )
    if await session.scalar(select(Nursery).where(Nursery.slug == slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Another nursery already has that address.")
    email = body.manager_email.lower()
    if await session.scalar(select(User).where(func.lower(User.email) == email)) or (
        await session.scalar(select(Operator).where(func.lower(Operator.email) == email))
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Someone already uses that email address.")
    problem = password_problem(body.manager_password)
    if problem:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)

    nursery = Nursery(name=body.name.strip(), slug=slug, timezone="Europe/London")
    session.add(nursery)
    await session.flush()
    session.add(
        User(
            nursery_id=nursery.id,
            email=email,
            full_name=body.manager_name.strip(),
            role=Role.ADMIN,
            password_hash=hash_password(body.manager_password),
        )
    )
    session.add(_log(operator, nursery, "nursery.created", f"first manager {email}"))
    await session.flush()
    return next(r for r in await nurseries(operator, session) if r.id == nursery.id)


async def _set_active(
    session: AsyncSession, operator: Operator, nursery_id: uuid.UUID, active: bool
) -> NurseryRow:
    nursery = await session.get(Nursery, nursery_id)
    if nursery is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such nursery.")
    if nursery.active != active:
        nursery.active = active
        session.add(
            _log(operator, nursery, "nursery.reactivated" if active else "nursery.suspended")
        )
        await session.flush()
    return next(r for r in await nurseries(operator, session) if r.id == nursery.id)


@router.post("/nurseries/{nursery_id}/suspend", response_model=NurseryRow)
async def suspend(
    nursery_id: uuid.UUID, operator: CurrentOperator, session: SessionDep
) -> NurseryRow:
    """Nobody at the nursery can sign in, and open sessions stop. Nothing is deleted."""
    return await _set_active(session, operator, nursery_id, False)


@router.post("/nurseries/{nursery_id}/reactivate", response_model=NurseryRow)
async def reactivate(
    nursery_id: uuid.UUID, operator: CurrentOperator, session: SessionDep
) -> NurseryRow:
    return await _set_active(session, operator, nursery_id, True)
