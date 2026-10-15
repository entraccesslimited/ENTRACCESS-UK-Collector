"""Request dependencies: the database session and who is asking."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Role, User
from app.security import COOKIE_NAME, read_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def current_user(
    request: Request,
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    if request.method not in _SAFE_METHODS and request.headers.get("X-Requested-With") != "fetch":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing request header.")
    user_id = read_session(token) if token else None
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    user = await session.scalar(select(User).where(User.id == user_id, User.active.is_(True)))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    return user


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
