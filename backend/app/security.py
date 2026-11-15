"""Passwords and sessions.

Sessions are a signed JWT in an HttpOnly, SameSite=Strict cookie. Script on
the page cannot read it, and a cross-site request does not carry it; every
request that changes something must also send `X-Requested-With`, which a
plain cross-site form cannot set.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

COOKIE_NAME = "collector_session"
_hasher = PasswordHasher()

# Verified against when the email is unknown, so a wrong email takes as long
# as a wrong password and the response time does not reveal who has an account.
_DUMMY_HASH = _hasher.hash("not-a-real-password-for-timing-only")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def password_problem(password: str) -> str | None:
    if len(password) < 10:
        return "Use at least 10 characters."
    if password.lower() in {"password123", "passwordpassword", "1234567890", "qwertyuiop"}:
        return "That password is too common."
    return None


USER = "user"
OPERATOR = "operator"


def issue_session(
    subject_id: uuid.UUID, kind: str = USER, *, lifetime: timedelta | None = None
) -> str:
    """A session for a nursery's user, or for a company operator.

    The kind is signed into the token, so a nursery user's session can never
    be read as an operator's, whatever ids happen to collide.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(subject_id),
        "kind": kind,
        "iat": int(now.timestamp()),
        "exp": int((now + (lifetime or timedelta(hours=settings.SESSION_HOURS))).timestamp()),
        "typ": "session",
    }
    return jwt.encode(claims, settings.SECRET_KEY, algorithm="HS256")


def read_session(token: str) -> tuple[str, uuid.UUID] | None:
    try:
        claims = jwt.decode(token, get_settings().SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if claims.get("typ") != "session" or claims.get("kind") not in (USER, OPERATOR):
        return None
    try:
        return str(claims["kind"]), uuid.UUID(str(claims["sub"]))
    except (KeyError, ValueError):
        return None


# What an invited account holds instead of a password hash. Not a hash of
# anything: argon2 cannot parse it, so `verify_password` fails closed and the
# account cannot be signed into until its owner chooses a password.
INVITED = "!invited"

# How long a link lasts. An invitation waits for somebody to notice it among
# a week's mail; a reset is for somebody standing at the sign-in page now.
INVITE_LINK = timedelta(days=7)
RESET_LINK = timedelta(hours=1)


def _fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def issue_password_link(user_id: uuid.UUID, password_hash: str, lifetime: timedelta) -> str:
    """A token that lets one person choose one new password, once.

    Single use with no table to track it: the token carries a fingerprint of
    the password hash it was issued against. Choosing a password changes the
    hash, so the same link — or any older one — no longer matches.
    """
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "pw": _fingerprint(password_hash),
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        "typ": "set-password",
    }
    return jwt.encode(claims, get_settings().SECRET_KEY, algorithm="HS256")


def read_password_link(token: str) -> tuple[uuid.UUID, str] | None:
    """The account a link is for, and the fingerprint it must still match."""
    try:
        claims = jwt.decode(token, get_settings().SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if claims.get("typ") != "set-password":
        return None
    try:
        return uuid.UUID(str(claims["sub"])), str(claims["pw"])
    except (KeyError, ValueError):
        return None


def link_still_fits(fingerprint: str, password_hash: str) -> bool:
    return hmac.compare_digest(fingerprint, _fingerprint(password_hash))
