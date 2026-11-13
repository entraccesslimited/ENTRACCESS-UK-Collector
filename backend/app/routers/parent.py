"""The parent portal: children, their collectors, passes and history."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import select

from app import collection
from app.config import get_settings
from app.deps import ParentUser, SessionDep
from app.models import Authorisation, Child, Handover, ParentLink, User
from app.schemas import (
    AuthorisationIn,
    AuthorisationOut,
    ChildOut,
    HandoverOut,
    PassOut,
    SharedIn,
)

router = APIRouter(prefix="/parent", tags=["parent"])


async def authorisation_out(
    session: SessionDep, auth: Authorisation, now: datetime
) -> AuthorisationOut:
    parent = await session.get(User, auth.authorised_by_id)
    return AuthorisationOut(
        id=auth.id,
        child_id=auth.child_id,
        collector_name=auth.collector_name,
        collector_relationship=auth.collector_relationship,
        collector_phone=auth.collector_phone,
        note_for_staff=auth.note_for_staff,
        kind=auth.kind,
        valid_from=auth.valid_from,
        valid_until=auth.valid_until,
        created_at=auth.created_at,
        revoked_at=auth.revoked_at,
        used_at=auth.used_at,
        status=collection.status_of(auth, now),
        authorised_by_name=parent.full_name if parent else "Unknown",
        source=auth.source,
    )


@router.get("/children", response_model=list[ChildOut])
async def my_children(parent: ParentUser, session: SessionDep) -> list[Child]:
    rows = await session.scalars(
        select(Child)
        .join(ParentLink, ParentLink.child_id == Child.id)
        .where(ParentLink.parent_id == parent.id, Child.nursery_id == parent.nursery_id)
        .order_by(Child.full_name)
    )
    return list(rows.all())


@router.get("/children/{child_id}/collectors", response_model=list[AuthorisationOut])
async def collectors(
    child_id: uuid.UUID, parent: ParentUser, session: SessionDep
) -> list[AuthorisationOut]:
    child = await collection.child_for_parent(session, parent, child_id)
    rows = await session.scalars(
        select(Authorisation)
        .where(Authorisation.child_id == child.id)
        .order_by(Authorisation.created_at.desc())
    )
    now = datetime.now(UTC)
    return [await authorisation_out(session, auth, now) for auth in rows.all()]


@router.post(
    "/children/{child_id}/collectors",
    response_model=AuthorisationOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_collector(
    child_id: uuid.UUID, body: AuthorisationIn, parent: ParentUser, session: SessionDep
) -> AuthorisationOut:
    auth = await collection.authorise(
        session,
        parent,
        child_id,
        collection.NewAuthorisation(**body.model_dump()),
    )
    return await authorisation_out(session, auth, datetime.now(UTC))


@router.post("/collectors/{authorisation_id}/revoke", response_model=AuthorisationOut)
async def revoke(
    authorisation_id: uuid.UUID, parent: ParentUser, session: SessionDep
) -> AuthorisationOut:
    auth = await collection.authorisation_for_parent(session, parent, authorisation_id)
    await collection.revoke(session, parent, auth)
    return await authorisation_out(session, auth, datetime.now(UTC))


@router.post("/collectors/{authorisation_id}/reissue", response_model=PassOut)
async def reissue(authorisation_id: uuid.UUID, parent: ParentUser, session: SessionDep) -> PassOut:
    auth = await collection.authorisation_for_parent(session, parent, authorisation_id)
    await collection.reissue(session, parent, auth)
    return await _pass(session, parent, auth)


@router.get("/collectors/{authorisation_id}/pass", response_model=PassOut)
async def get_pass(authorisation_id: uuid.UUID, parent: ParentUser, session: SessionDep) -> PassOut:
    auth = await collection.authorisation_for_parent(session, parent, authorisation_id)
    return await _pass(session, parent, auth)


async def _pass(session: SessionDep, parent: User, auth: Authorisation) -> PassOut:
    return await pass_out(session, parent, auth)


async def pass_out(session: SessionDep, user: User, auth: Authorisation) -> PassOut:
    nursery = await collection.nursery_of(session, user)
    child = await session.get(Child, auth.child_id)
    now = datetime.now(UTC)
    token = collection.pass_for(auth)
    return PassOut(
        authorisation_id=auth.id,
        token=token,
        code_today=collection.code_for(nursery, auth, now),
        share_url=f"{get_settings().APP_BASE_URL}/pass/{token}",
        status=collection.status_of(auth, now),
        nursery_name=nursery.name,
        child_first_name=child.full_name.split()[0] if child else "",
    )


CHANNELS = {
    "whatsapp": "WhatsApp",
    "sms": "text message",
    "email": "email",
    "share": "the phone's share menu",
    "copy": "a copied link",
}


async def record_shared(
    session: SessionDep, user: User, auth: Authorisation, body: SharedIn
) -> None:
    """Note how a pass was sent. The sending itself happens on the sharer's phone."""
    what = "today's code" if body.what == "code" else "pass link"
    await collection.audit(
        session,
        nursery_id=auth.nursery_id,
        actor=user,
        action="pass.shared",
        subject_id=auth.id,
        detail=f"{what} for {auth.collector_name} by {CHANNELS[body.channel]}",
    )


@router.post("/collectors/{authorisation_id}/shared", status_code=status.HTTP_204_NO_CONTENT)
async def shared(
    authorisation_id: uuid.UUID, body: SharedIn, parent: ParentUser, session: SessionDep
) -> None:
    auth = await collection.authorisation_for_parent(session, parent, authorisation_id)
    await record_shared(session, parent, auth, body)


@router.get("/handovers", response_model=list[HandoverOut])
async def history(parent: ParentUser, session: SessionDep) -> list[Handover]:
    rows = await session.scalars(
        select(Handover)
        .join(ParentLink, ParentLink.child_id == Handover.child_id)
        .where(ParentLink.parent_id == parent.id, Handover.nursery_id == parent.nursery_id)
        .order_by(Handover.occurred_at.desc())
        .limit(200)
    )
    return list(rows.all())
