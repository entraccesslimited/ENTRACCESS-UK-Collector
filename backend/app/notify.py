"""Telling parents about a handover.

Every parent linked to the child hears about a release or a refusal, not only
the one who authorised the collector: both parents have a right to know who
their child left with. Delivery failures are logged and never undo the
handover, which has already happened at the door.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import aiosmtplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Handover, HandoverOutcome, Nursery, ParentLink, User

log = logging.getLogger("collector.notify")


@dataclass
class Outbox:
    """Messages not sent because email is off. Read by the tests and in dev."""

    messages: list[EmailMessage] = field(default_factory=list)


OUTBOX = Outbox()


def _compose(handover: Handover, nursery: Nursery, to: str) -> EmailMessage:
    when = handover.occurred_at.astimezone(ZoneInfo(nursery.timezone)).strftime("%H:%M on %d %b")
    message = EmailMessage()
    message["From"] = get_settings().EMAIL_FROM
    message["To"] = to
    if handover.outcome is HandoverOutcome.RELEASED:
        message["Subject"] = f"{handover.child_name} has been collected"
        body = (
            f"{handover.child_name} was collected from {nursery.name} at {when} by "
            f"{handover.collector_name} ({handover.collector_relationship}), authorised by "
            f"{handover.authorised_by_name}. Checked by {handover.staff_name}.\n\n"
            "If you did not expect this, call the nursery now."
        )
    else:
        message["Subject"] = f"{handover.child_name} was not released"
        body = (
            f"At {when}, {handover.collector_name} came to collect {handover.child_name} from "
            f"{nursery.name}, and staff did not release them. Reason given: "
            f"{handover.refusal_reason}.\n\nYour child is safe at the nursery. "
            "Please call the nursery to arrange collection."
        )
    message.set_content(body)
    return message


async def send(to: str, subject: str, body: str, *, reply_to: str | None = None) -> None:
    """Send one plain message, or keep it in the outbox when email is off."""
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)
    if not settings.EMAIL_ENABLED:
        OUTBOX.messages.append(message)
        return
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_STARTTLS,
            timeout=15,
        )
    except (aiosmtplib.SMTPException, OSError):
        log.exception("could not send %s", subject)


async def notify_parents(session: AsyncSession, handover: Handover) -> None:
    nursery = await session.get(Nursery, handover.nursery_id)
    assert nursery is not None
    parents = (
        await session.scalars(
            select(User)
            .join(ParentLink, ParentLink.parent_id == User.id)
            .where(ParentLink.child_id == handover.child_id, User.active.is_(True))
        )
    ).all()
    settings = get_settings()
    for parent in parents:
        message = _compose(handover, nursery, parent.email)
        if not settings.EMAIL_ENABLED:
            OUTBOX.messages.append(message)
            log.info("email not sent (EMAIL_ENABLED is off): %s", message["Subject"])
            continue
        try:
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                start_tls=settings.SMTP_STARTTLS,
                timeout=15,
            )
        except (aiosmtplib.SMTPException, OSError):
            log.exception("could not email a handover notice")
