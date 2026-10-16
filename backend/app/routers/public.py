"""The collector's own view of their pass, opened from the link a parent shares.

No sign-in: the collector has no account, and the pass in the link is the
credential. It shows the child's first name only and nothing about the family,
so a forwarded link reveals as little as possible.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status

from app import collection, passes
from app.config import get_settings
from app.deps import SessionDep
from app.models import Authorisation, CheckResult, Child, Enquiry, Nursery
from app.notify import send
from app.schemas import INTERESTS, UK_REGIONS, EnquiryIn, PublicPassOut

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


# Enquiries per address, kept in memory: enough to stop a script filling the
# company portal, not a substitute for a proper limit behind several processes.
ENQUIRY_LIMIT = 5
ENQUIRY_WINDOW = timedelta(hours=1)
_enquiries: dict[str, list[datetime]] = defaultdict(list)


@router.post("/enquiries", status_code=status.HTTP_201_CREATED)
async def enquire(body: EnquiryIn, request: Request, session: SessionDep) -> dict[str, str]:
    """The website's contact form. Public, so it is rate-limited and bot-trapped."""
    thanks = {"message": "Thank you. We will reply within two working days."}
    if body.website:
        # The hidden field was filled: a bot. Say thank you and keep nothing.
        return thanks
    address = request.client.host if request.client else "unknown"
    now = datetime.now(UTC)
    recent = [t for t in _enquiries[address] if now - t < ENQUIRY_WINDOW]
    if len(recent) >= ENQUIRY_LIMIT:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many enquiries from here. Please email us."
        )
    region = body.region if body.region in UK_REGIONS else None
    interest = body.interest if body.interest in INTERESTS else None
    enquiry = Enquiry(
        contact_name=body.contact_name.strip(),
        nursery_name=body.nursery_name.strip(),
        email=body.email.lower(),
        phone=(body.phone or "").strip() or None,
        region=region,
        children=(body.children or "").strip() or None,
        interest=interest,
        message=(body.message or "").strip() or None,
    )
    session.add(enquiry)
    await session.flush()
    _enquiries[address] = [*recent, now]
    support = get_settings().SUPPORT_EMAIL
    if support:
        await send(
            support,
            f"Website enquiry: {enquiry.nursery_name}",
            "\n".join(
                f"{label}: {value}"
                for label, value in (
                    ("From", f"{enquiry.contact_name} <{enquiry.email}>"),
                    ("Nursery", enquiry.nursery_name),
                    ("Phone", enquiry.phone),
                    ("Region", enquiry.region),
                    ("Children", enquiry.children),
                    ("Interested in", enquiry.interest),
                    ("Message", enquiry.message),
                )
                if value
            ),
            reply_to=enquiry.email,
        )
    return thanks
