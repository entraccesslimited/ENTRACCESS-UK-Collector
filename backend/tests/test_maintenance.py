"""The maintenance jobs that tidy up after a test run on the live site."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.maintenance import purge_test_accounts
from app.models import Child, Nursery, Operator, User
from tests.conftest import World


async def counts(session: AsyncSession) -> tuple[int, int, int]:
    session.expire_all()
    return (
        await session.scalar(select(func.count()).select_from(Nursery)) or 0,
        await session.scalar(select(func.count()).select_from(User)) or 0,
        await session.scalar(select(func.count()).select_from(Child)) or 0,
    )


async def test_listing_removes_nothing(session: AsyncSession, world: World) -> None:
    del world
    before = await counts(session)
    assert await purge_test_accounts.purge("acorns.example.com", apply=False) == 0
    assert await counts(session) == before


async def test_a_test_nursery_goes_and_a_real_one_stays(
    session: AsyncSession, world: World
) -> None:
    del world
    session.add(Operator(email="op@acorns.example.com", full_name="Test Op", password_hash="x"))
    await session.commit()

    assert await purge_test_accounts.purge("acorns.example.com", apply=True) == 0

    nurseries = (await session.scalars(select(Nursery.slug))).all()
    assert nurseries == ["oak-tree"]
    emails = sorted((await session.scalars(select(User.email))).all())
    assert emails == ["parent@oak.example.com", "staff@oak.example.com"]
    assert (await session.scalars(select(Child.full_name))).all() == ["Ola Oak"]
    assert (await session.scalars(select(Operator.email))).all() == ["ops@entraccess.example.com"]


async def test_a_nursery_with_anyone_else_in_it_is_kept(
    session: AsyncSession, world: World
) -> None:
    """Only the test accounts go; the nursery stays while a real person is in it."""
    del world
    assert await purge_test_accounts.purge("oak.example.com", apply=True) == 0
    session.expire_all()
    # Oak Tree's people were all at oak.example.com, so it went too; Little
    # Acorns is untouched.
    assert (await session.scalars(select(Nursery.slug))).all() == ["little-acorns"]


def test_only_a_reserved_domain_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["purge", "--domain", "gmail.com", "--yes"])
    with pytest.raises(SystemExit) as stopped:
        purge_test_accounts.main()
    assert "not a reserved test domain" in str(stopped.value)
