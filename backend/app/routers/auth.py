"""Signing in and out."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.config import get_settings
from app.deps import CurrentUser, SessionDep
from app.models import Nursery, User
from app.schemas import Me, SignIn
from app.security import COOKIE_NAME, issue_session, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Failed sign-ins per email, kept in memory. One process per deployment is the
# expected shape here; behind several, put this in the database or Redis.
MAX_FAILURES = 10
FAILURE_WINDOW = timedelta(minutes=15)
_failures: dict[str, list[datetime]] = defaultdict(list)


def _recent_failures(email: str, now: datetime) -> list[datetime]:
    recent = [t for t in _failures[email] if now - t < FAILURE_WINDOW]
    _failures[email] = recent
    return recent


def _me(user: User, nursery: Nursery) -> Me:
    return Me(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        nursery_name=nursery.name,
    )


@router.post("/sign-in", response_model=Me)
async def sign_in(body: SignIn, response: Response, session: SessionDep) -> Me:
    email = body.email.lower()
    now = datetime.now(UTC)
    if len(_recent_failures(email, now)) >= MAX_FAILURES:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again in 15 minutes."
        )
    user = await session.scalar(select(User).where(func.lower(User.email) == email))
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        _failures[email].append(now)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That email and password do not match.")
    _failures.pop(email, None)
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been switched off.")
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        issue_session(user.id),
        max_age=settings.SESSION_HOURS * 3600,
        httponly=True,
        samesite="strict",
        secure=settings.secure_cookies,
        path="/",
    )
    nursery = await session.get(Nursery, user.nursery_id)
    assert nursery is not None
    return _me(user, nursery)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(response: Response, _user: CurrentUser) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=Me)
async def me(user: CurrentUser, session: SessionDep) -> Me:
    nursery = await session.get(Nursery, user.nursery_id)
    assert nursery is not None
    return _me(user, nursery)
