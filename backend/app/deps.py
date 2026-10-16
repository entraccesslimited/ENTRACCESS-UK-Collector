"""Request dependencies: the database session and who is asking."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Nursery, Operator, Role, User
from app.security import COOKIE_NAME, OPERATOR, USER, read_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _session_of(request: Request, token: str | None) -> tuple[str, uuid.UUID]:
    if request.method not in _SAFE_METHODS and request.headers.get("X-Requested-With") != "fetch":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing request header.")
    found = read_session(token) if token else None
    if found is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    return found


async def current_user(
    request: Request,
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    """A nursery's own user, from an active account at an active nursery."""
    kind, user_id = _session_of(request, token)
    if kind != USER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is for nursery accounts.")
    user = await session.scalar(
        select(User)
        .join(Nursery, Nursery.id == User.nursery_id)
        .where(User.id == user_id, User.active.is_(True), Nursery.active.is_(True))
    )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    return user


async def current_operator(
    request: Request,
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> Operator:
    """Someone at ENTRACCESS UK, signed in to the company portal."""
    kind, operator_id = _session_of(request, token)
    if kind != OPERATOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is for the company portal.")
    operator = await session.scalar(
        select(Operator).where(Operator.id == operator_id, Operator.active.is_(True))
    )
    if operator is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    return operator


CurrentOperator = Annotated[Operator, Depends(current_operator)]


CurrentUser = Annotated[User, Depends(current_user)]


def require(*roles: Role) -> Callable[[User], Coroutine[Any, Any, User]]:
    async def check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this.")
        return user

    return check


ParentUser = Annotated[User, Depends(require(Role.PARENT))]
StaffUser = Annotated[User, Depends(require(Role.STAFF, Role.ADMIN))]
AdminUser = Annotated[User, Depends(require(Role.ADMIN))]
