"""How long a sign-in lasts: long on a parent's own phone, short on shared devices."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from tests.conftest import PASSWORD, World


async def _cookie_max_age(app: object, email: str) -> int:
    async with AsyncClient(
        transport=ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
        headers={"X-Requested-With": "fetch"},
    ) as client:
        response = await client.post(
            "/api/auth/sign-in", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        header = response.headers["set-cookie"]
        return int(header.split("Max-Age=")[1].split(";")[0])


async def test_a_parent_stays_signed_in_for_a_month(app: object, world: World) -> None:
    assert await _cookie_max_age(app, world.parent.email) == 30 * 24 * 3600


async def test_staff_and_the_company_keep_the_short_session(app: object, world: World) -> None:
    assert await _cookie_max_age(app, world.staff.email) == 12 * 3600
    assert await _cookie_max_age(app, world.admin.email) == 12 * 3600
    assert await _cookie_max_age(app, "ops@entraccess.example.com") == 12 * 3600
