"""Passwords and sessions.

Sessions are a signed JWT in an HttpOnly, SameSite=Strict cookie. Script on
the page cannot read it, and a cross-site request does not carry it; every
request that changes something must also send `X-Requested-With`, which a
plain cross-site form cannot set.
"""

from __future__ import annotations

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


def issue_session(subject_id: uuid.UUID, kind: str = USER) -> str:
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
        "exp": int((now + timedelta(hours=settings.SESSION_HOURS)).timestamp()),
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
