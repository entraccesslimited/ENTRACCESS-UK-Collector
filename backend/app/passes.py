"""Collector passes and daily codes.

A pass is `CP1.<payload>.<signature>`: the authorisation's id and version,
signed with a key derived for that nursery alone. It proves the pass was
issued by this nursery for this authorisation, and nothing else — it carries
no name, no child and no date, so a pass found in a car park tells the finder
nothing. Whether it is still good (revoked, expired, already used) is always
answered by the database at the door, never by the pass.

The daily code is six digits derived from the same id and version and the
nursery's local date. It is for the collector without a phone: a parent reads
it out over the phone and staff type it in against the child.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import uuid
from dataclasses import dataclass
from datetime import date

from app.config import get_settings

PREFIX = "CP1"
_PAYLOAD = struct.Struct(">16sI")


class InvalidPass(ValueError):
    """The text is not a pass this nursery issued."""


@dataclass(frozen=True, slots=True)
class PassPayload:
    authorisation_id: uuid.UUID
    version: int


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def nursery_key(nursery_id: uuid.UUID) -> bytes:
    """A key for one nursery, so one nursery's pass never verifies at another."""
    master = get_settings().PASS_SIGNING_KEY.encode("utf-8")
    return hmac.new(master, b"collector-nursery:" + nursery_id.bytes, hashlib.sha256).digest()


def issue_pass(nursery_id: uuid.UUID, authorisation_id: uuid.UUID, version: int) -> str:
    payload = _PAYLOAD.pack(authorisation_id.bytes, version)
    signature = hmac.new(nursery_key(nursery_id), b"pass:" + payload, hashlib.sha256).digest()
    return f"{PREFIX}.{_b64(payload)}.{_b64(signature[:16])}"


def read_pass(token: str, *, nursery_id: uuid.UUID) -> PassPayload:
    """Verify a pass against one nursery's key and return what it names."""
    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise InvalidPass("Not a collector pass.")
    try:
        payload = _unb64(parts[1])
        signature = _unb64(parts[2])
    except (ValueError, TypeError) as exc:
        raise InvalidPass("Not a collector pass.") from exc
    if len(payload) != _PAYLOAD.size:
        raise InvalidPass("Not a collector pass.")
    expected = hmac.new(nursery_key(nursery_id), b"pass:" + payload, hashlib.sha256).digest()
    if not hmac.compare_digest(expected[:16], signature):
        raise InvalidPass("This pass was not issued by this nursery.")
    raw_id, version = _PAYLOAD.unpack(payload)
    return PassPayload(authorisation_id=uuid.UUID(bytes=raw_id), version=version)


def daily_code(nursery_id: uuid.UUID, authorisation_id: uuid.UUID, version: int, day: date) -> str:
    """Six digits, the same all day in the nursery's local time, new tomorrow."""
    message = (
        b"code:" + authorisation_id.bytes + struct.pack(">I", version) + day.isoformat().encode()
    )
    digest = hmac.new(nursery_key(nursery_id), message, hashlib.sha256).digest()
    number = int.from_bytes(digest[:8], "big") % 1_000_000
    return f"{number:06d}"


def codes_match(given: str, expected: str) -> bool:
    cleaned = "".join(ch for ch in given if ch.isdigit())
    return hmac.compare_digest(cleaned.encode(), expected.encode())


def peek_authorisation_id(token: str) -> uuid.UUID | None:
    """The authorisation a pass names, *without* verifying it.

    Only for finding which nursery's key to verify with; the caller must then
    call `read_pass` with that nursery's id before trusting anything.
    """
    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        return None
    try:
        payload = _unb64(parts[1])
    except (ValueError, TypeError):
        return None
    if len(payload) != _PAYLOAD.size:
        return None
    raw_id, _version = _PAYLOAD.unpack(payload)
    return uuid.UUID(bytes=raw_id)
