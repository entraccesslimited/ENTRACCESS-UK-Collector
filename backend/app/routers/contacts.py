"""Nursery contacts: collectors the setting holds from registration forms."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app import collection, contacts
from app.deps import AdminUser, SessionDep
from app.models import Authorisation, CollectorKind, CollectorSource
from app.routers.parent import authorisation_out, pass_out, record_shared
from app.schemas import (
    AuthorisationOut,
    ContactImportIn,
    ContactImportOut,
    ContactIn,
    PassOut,
    SharedIn,
)

router = APIRouter(prefix="/admin", tags=["contacts"])


@router.post(
    "/children/{child_id}/contacts",
    response_model=AuthorisationOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_contact(
    child_id: uuid.UUID, body: ContactIn, admin: AdminUser, session: SessionDep
) -> AuthorisationOut:
    auth = await contacts.add_one(
        session,
        admin,
        child_id,
        collection.NewAuthorisation(
            collector_name=body.collector_name,
            collector_relationship=body.collector_relationship,
            collector_phone=body.collector_phone,
            kind=CollectorKind.REGULAR,
            note_for_staff=body.note_for_staff,
            start_date=body.start_date,
            end_date=body.end_date,
        ),
    )
    return await authorisation_out(session, auth, datetime.now(UTC))


@router.post("/contacts/import", response_model=ContactImportOut)
async def import_contacts(
    body: ContactImportIn, admin: AdminUser, session: SessionDep
) -> ContactImportOut:
    """Columns: Child, Contact name, Relationship, Phone, and optionally Password."""
    result = await contacts.import_contacts(session, admin, body.csv)
    await contacts.tell_parents(session, await collection.nursery_of(session, admin), result.added)
    return ContactImportOut(
        added=len(result.added),
        skipped=result.skipped,
        collectors=[a.collector_name for a in result.added],
    )


async def _contact(
    session: SessionDep, admin: AdminUser, authorisation_id: uuid.UUID
) -> Authorisation:
    """A nursery contact at this nursery. A parent's own collectors stay with the parent."""
    auth = await session.scalar(
        select(Authorisation).where(
            Authorisation.id == authorisation_id,
            Authorisation.nursery_id == admin.nursery_id,
        )
    )
    if auth is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such collector.")
    if auth.source is not CollectorSource.SETTING:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the parent can send the pass of a collector they added.",
        )
    return auth


@router.get("/collectors/{authorisation_id}/pass", response_model=PassOut)
async def contact_pass(
    authorisation_id: uuid.UUID, admin: AdminUser, session: SessionDep
) -> PassOut:
    return await pass_out(session, admin, await _contact(session, admin, authorisation_id))


@router.post("/collectors/{authorisation_id}/reissue", response_model=PassOut)
async def contact_reissue(
    authorisation_id: uuid.UUID, admin: AdminUser, session: SessionDep
) -> PassOut:
    auth = await _contact(session, admin, authorisation_id)
    await collection.reissue(session, admin, auth)
    return await pass_out(session, admin, auth)


@router.post("/collectors/{authorisation_id}/shared", status_code=status.HTTP_204_NO_CONTENT)
async def contact_shared(
    authorisation_id: uuid.UUID, body: SharedIn, admin: AdminUser, session: SessionDep
) -> None:
    await record_shared(session, admin, await _contact(session, admin, authorisation_id), body)
