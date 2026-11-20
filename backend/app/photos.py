"""Photos of collectors, so staff can recognise who they are handing a child to.

A photo is optional and small. The parent's phone shrinks and re-encodes it
before sending, which also drops the camera's location data; the server
accepts only JPEG, PNG or WebP under a size cap, judged by the bytes
themselves rather than by what the upload claims to be.

It exists for one purpose, recognising someone at the door, so it does not
outlive it: removing a collector deletes their photo, as does a one-off
collection happening and an authorisation running out.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collection import CollectionError, audit
from app.models import Authorisation, CollectorPhoto, User

MAX_BYTES = 300_000


def _kind(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def decode(data_url: str) -> tuple[str, bytes]:
    """The image type and bytes from a `data:` URL, or a refusal staff can read."""
    _, _, encoded = data_url.partition(",")
    try:
        data = base64.b64decode(encoded or data_url, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CollectionError("That photo could not be read. Try another.") from exc
    if len(data) > MAX_BYTES:
        raise CollectionError("That photo is too large. Try a smaller one.")
    kind = _kind(data)
    if kind is None:
        raise CollectionError("Use a JPEG, PNG or WebP photo.")
    return kind, data


async def save(session: AsyncSession, actor: User, auth: Authorisation, data_url: str) -> None:
    if auth.revoked_at is not None or auth.used_at is not None:
        raise CollectionError("This collector can no longer collect, so needs no photo.")
    kind, data = decode(data_url)
    existing = await session.get(CollectorPhoto, auth.id)
    if existing is None:
        session.add(
            CollectorPhoto(
                authorisation_id=auth.id, nursery_id=auth.nursery_id, content_type=kind, data=data
            )
        )
    else:
        existing.content_type, existing.data = kind, data
        existing.created_at = datetime.now(UTC)
    await audit(
        session,
        nursery_id=auth.nursery_id,
        actor=actor,
        action="photo.added",
        subject_id=auth.id,
        detail=auth.collector_name,
    )


async def remove(session: AsyncSession, actor: User | None, auth: Authorisation) -> bool:
    photo = await session.get(CollectorPhoto, auth.id)
    if photo is None:
        return False
    await session.delete(photo)
    await audit(
        session,
        nursery_id=auth.nursery_id,
        actor=actor,
        action="photo.removed",
        subject_id=auth.id,
        detail=auth.collector_name,
    )
    return True


async def has_photo(session: AsyncSession, authorisation_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(CollectorPhoto.authorisation_id).where(
            CollectorPhoto.authorisation_id == authorisation_id
        )
    )
    return found is not None


async def get(session: AsyncSession, authorisation_id: uuid.UUID) -> CollectorPhoto | None:
    return await session.get(CollectorPhoto, authorisation_id)


async def purge_unneeded(session: AsyncSession, now: datetime) -> int:
    """Delete the photos of collectors who can no longer collect."""
    finished = select(Authorisation.id).where(
        or_(
            Authorisation.revoked_at.is_not(None),
            Authorisation.used_at.is_not(None),
            Authorisation.valid_until < now,
        )
    )
    result = await session.execute(
        delete(CollectorPhoto).where(CollectorPhoto.authorisation_id.in_(finished))
    )
    return int(getattr(result, "rowcount", 0) or 0)
