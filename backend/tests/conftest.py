"""Test fixtures: a fresh database per test, two nurseries, and signed-in clients."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app import db
from app.main import create_app
from app.models import Child, Nursery, ParentLink, Role, User
from app.notify import OUTBOX
from app.routers import auth as auth_router
from app.security import hash_password

PASSWORD = "correct-horse-battery"


@dataclass
class World:
    nursery: Nursery
    other_nursery: Nursery
    admin: User
    staff: User
    parent: User
    second_parent: User
    other_parent: User
    other_staff: User
    child: Child
    sibling: Child
    unrelated_child: Child
    other_child: Child


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[object]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(db.Base.metadata.create_all)
    db.use_engine(engine)
    OUTBOX.messages.clear()
    auth_router._failures.clear()
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: object) -> AsyncIterator[AsyncSession]:  # noqa: ARG001
    async with db.sessionmaker()() as s:
        yield s


@pytest.fixture
async def world(session: AsyncSession) -> World:
    nursery = Nursery(name="Little Acorns (demo)", slug="little-acorns", timezone="Europe/London")
    other = Nursery(name="Oak Tree (demo)", slug="oak-tree", timezone="Europe/London")
    session.add_all([nursery, other])
    await session.flush()

    def person(n: Nursery, email: str, name: str, role: Role) -> User:
        return User(
            nursery_id=n.id,
            email=email,
            full_name=name,
            role=role,
            password_hash=hash_password(PASSWORD),
        )

    admin = person(nursery, "admin@acorns.example.com", "Amira Admin", Role.ADMIN)
    staff = person(nursery, "staff@acorns.example.com", "Sam Staff", Role.STAFF)
    parent = person(nursery, "parent@acorns.example.com", "Priya Parent", Role.PARENT)
    second = person(nursery, "dad@acorns.example.com", "Dev Parent", Role.PARENT)
    other_parent = person(other, "parent@oak.example.com", "Olu Parent", Role.PARENT)
    other_staff = person(other, "staff@oak.example.com", "Otto Staff", Role.STAFF)
    session.add_all([admin, staff, parent, second, other_parent, other_staff])

    child = Child(nursery_id=nursery.id, full_name="Maya Parent", room="Butterflies")
    sibling = Child(nursery_id=nursery.id, full_name="Leo Parent", room="Caterpillars")
    unrelated = Child(nursery_id=nursery.id, full_name="Zara Other", room="Butterflies")
    other_child = Child(nursery_id=other.id, full_name="Ola Oak", room="Acorns")
    session.add_all([child, sibling, unrelated, other_child])
    await session.flush()
    session.add_all(
        [
            ParentLink(nursery_id=nursery.id, parent_id=parent.id, child_id=child.id),
            ParentLink(nursery_id=nursery.id, parent_id=parent.id, child_id=sibling.id),
            ParentLink(nursery_id=nursery.id, parent_id=second.id, child_id=child.id),
            ParentLink(nursery_id=other.id, parent_id=other_parent.id, child_id=other_child.id),
        ]
    )
    await session.commit()
    return World(
        nursery,
        other,
        admin,
        staff,
        parent,
        second,
        other_parent,
        other_staff,
        child,
        sibling,
        unrelated,
        other_child,
    )


@pytest.fixture
def app(engine: object) -> object:  # noqa: ARG001
    return create_app()


@asynccontextmanager
async def signed_in(app: object, email: str) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
        headers={"X-Requested-With": "fetch"},
    ) as client:
        response = await client.post(
            "/api/auth/sign-in", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        yield client


@pytest.fixture
async def as_parent(app: object, world: World) -> AsyncIterator[AsyncClient]:
    async with signed_in(app, world.parent.email) as c:
        yield c


@pytest.fixture
async def as_staff(app: object, world: World) -> AsyncIterator[AsyncClient]:
    async with signed_in(app, world.staff.email) as c:
        yield c


@pytest.fixture
async def as_admin(app: object, world: World) -> AsyncIterator[AsyncClient]:
    async with signed_in(app, world.admin.email) as c:
        yield c


@pytest.fixture
async def as_other_staff(app: object, world: World) -> AsyncIterator[AsyncClient]:
    async with signed_in(app, world.other_staff.email) as c:
        yield c


@pytest.fixture
async def as_other_parent(app: object, world: World) -> AsyncIterator[AsyncClient]:
    async with signed_in(app, world.other_parent.email) as c:
        yield c


@pytest.fixture
async def anonymous(app: object) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:  # type: ignore[arg-type]
        yield c
