"""Signing in and out."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from sqlalchemy import func, select

from app.config import get_settings
from app.deps import SessionDep
from app.models import Nursery, Operator, Role, User
from app.schemas import Me, SignIn
from app.security import (
    COOKIE_NAME,
    OPERATOR,
    USER,
    issue_session,
    read_session,
    verify_password,
)

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


COMPANY_NAME = "ENTRACCESS UK"


def _me(user: User, nursery: Nursery) -> Me:
    return Me(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        nursery_name=nursery.name,
    )


def _operator_me(operator: Operator) -> Me:
    return Me(
        id=operator.id,
        email=operator.email,
        full_name=operator.full_name,
        role="operator",
        nursery_name=COMPANY_NAME,
    )


def _set_cookie(response: Response, token: str, lifetime: timedelta | None = None) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int((lifetime or timedelta(hours=settings.SESSION_HOURS)).total_seconds()),
        httponly=True,
        samesite="strict",
        secure=settings.secure_cookies,
        path="/",
    )


@router.post("/sign-in", response_model=Me)
async def sign_in(body: SignIn, response: Response, session: SessionDep) -> Me:
    """One sign-in for every portal; the account decides which portal opens."""
    email = body.email.lower()
    now = datetime.now(UTC)
    if len(_recent_failures(email, now)) >= MAX_FAILURES:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again in 15 minutes."
        )
    user = await session.scalar(select(User).where(func.lower(User.email) == email))
    operator = (
        None
        if user is not None
        else await session.scalar(select(Operator).where(func.lower(Operator.email) == email))
    )
    account: User | Operator | None = user or operator
    if not verify_password(body.password, account.password_hash if account else None):
        _failures[email].append(now)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That email and password do not match.")
    _failures.pop(email, None)
    assert account is not None
    if not account.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been switched off.")

    if isinstance(account, Operator):
        _set_cookie(response, issue_session(account.id, OPERATOR))
        return _operator_me(account)

    nursery = await session.get(Nursery, account.nursery_id)
    assert nursery is not None
    if not nursery.active:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This nursery's account is suspended. Please contact ENTRACCESS UK.",
        )
    lifetime = timedelta(days=get_settings().PARENT_SESSION_DAYS) if account.role is Role.PARENT else None
    _set_cookie(response, issue_session(account.id, USER, lifetime=lifetime), lifetime)
    return _me(account, nursery)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(request: Request, response: Response) -> None:
    if request.headers.get("X-Requested-With") != "fetch":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing request header.")
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=Me)
async def me(
    session: SessionDep, token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None
) -> Me:
    found = read_session(token) if token else None
    if found is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    kind, subject = found
    if kind == OPERATOR:
        operator = await session.get(Operator, subject)
        if operator is None or not operator.active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
        return _operator_me(operator)
    user = await session.get(User, subject)
    nursery = await session.get(Nursery, user.nursery_id) if user else None
    if user is None or not user.active or nursery is None or not nursery.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    return _me(user, nursery)
