"""The collector's own view of their pass, opened from the link a parent shares.

No sign-in: the collector has no account, and the pass in the link is the
credential. It shows the child's first name only and nothing about the family,
so a forwarded link reveals as little as possible.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app import collection, passes
from app.deps import SessionDep
from app.models import Authorisation, CheckResult, Child, Nursery
from app.schemas import PublicPassOut

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/pass/{token}", response_model=PublicPassOut)
async def view_pass(token: str, session: SessionDep) -> PublicPassOut:
    not_found = HTTPException(status.HTTP_404_NOT_FOUND, "This pass is not valid.")
    auth_id = passes.peek_authorisation_id(token)
    auth = await session.get(Authorisation, auth_id) if auth_id else None
    nursery = await session.get(Nursery, auth.nursery_id) if auth else None
    if auth is None or nursery is None or not nursery.active:
        raise not_found
    try:
        payload = passes.read_pass(token, nursery_id=auth.nursery_id)
    except passes.InvalidPass as exc:
        raise not_found from exc
    child = await session.get(Child, auth.child_id)
    assert child is not None
    result = collection.status_of(auth, datetime.now(UTC))
    if payload.version != auth.version:
        result = CheckResult.REISSUED
    return PublicPassOut(
        nursery_name=nursery.name,
        collector_name=auth.collector_name,
        child_first_name=child.full_name.split()[0],
        kind=auth.kind,
        valid_from=auth.valid_from,
        valid_until=auth.valid_until,
        status=result,
        token=token,
    )
