"""The company portal: ENTRACCESS UK running every nursery."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from tests.conftest import PASSWORD, World

NEW = {
    "name": "Rosebud Nursery (demo)",
    "slug": "rosebud",
    "manager_name": "Rosa Manager",
    "manager_email": "rosa@rosebud.example.com",
    "manager_password": "a-long-enough-password",
}


async def test_an_operator_signs_in_to_the_company_portal(as_operator: AsyncClient) -> None:
    me = (await as_operator.get("/api/auth/me")).json()
    assert me["role"] == "operator"
    assert me["nursery_name"] == "ENTRACCESS UK"


async def test_the_list_counts_but_never_names_a_child(
    world: World, as_parent: AsyncClient, as_operator: AsyncClient
) -> None:
    await as_parent.post(
        f"/api/parent/children/{world.child.id}/collectors",
        json={
            "collector_name": "Grace Grandma",
            "collector_relationship": "Grandparent",
            "collector_phone": "07700 900123",
            "kind": "regular",
        },
    )
    response = await as_operator.get("/api/company/nurseries")
    assert response.status_code == 200
    rows = {r["slug"]: r for r in response.json()}
    acorns = rows["little-acorns"]
    assert acorns["children"] == 3
    assert acorns["parents"] == 2
    assert acorns["room_leaders"] == 1
    assert acorns["managers"] == 1
    assert acorns["active_collectors"] == 1
    for name in ("Maya", "Grace", "Priya"):
        assert name not in response.text
    overview = (await as_operator.get("/api/company/overview")).json()
    assert overview["nurseries"] == 2
    assert overview["children"] == 4


async def test_setting_up_a_nursery_makes_its_first_manager(
    app: object, as_operator: AsyncClient
) -> None:
    created = await as_operator.post("/api/company/nurseries", json=NEW)
    assert created.status_code == 201, created.text
    assert created.json()["managers"] == 1
    async with AsyncClient(
        transport=ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
        headers={"X-Requested-With": "fetch"},
    ) as client:
        signed = await client.post(
            "/api/auth/sign-in",
            json={"email": NEW["manager_email"], "password": NEW["manager_password"]},
        )
        assert signed.status_code == 200
        assert signed.json()["role"] == "admin"
        assert signed.json()["nursery_name"] == NEW["name"]


async def test_addresses_and_emails_are_not_taken_twice(as_operator: AsyncClient) -> None:
    taken_slug = {**NEW, "slug": "little-acorns"}
    assert (await as_operator.post("/api/company/nurseries", json=taken_slug)).status_code == 409
    taken_email = {**NEW, "manager_email": "admin@acorns.example.com"}
    assert (await as_operator.post("/api/company/nurseries", json=taken_email)).status_code == 409
    bad_slug = {**NEW, "slug": "Not A Slug"}
    assert (await as_operator.post("/api/company/nurseries", json=bad_slug)).status_code == 400


async def test_suspending_stops_sign_in_and_open_sessions(
    app: object, world: World, as_operator: AsyncClient, as_admin: AsyncClient
) -> None:
    assert (await as_admin.get("/api/admin/today")).status_code == 200
    r = await as_operator.post(f"/api/company/nurseries/{world.nursery.id}/suspend")
    assert r.json()["active"] is False
    assert (await as_admin.get("/api/admin/today")).status_code == 401
    async with AsyncClient(
        transport=ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
        headers={"X-Requested-With": "fetch"},
    ) as client:
        blocked = await client.post(
            "/api/auth/sign-in", json={"email": world.staff.email, "password": PASSWORD}
        )
        assert blocked.status_code == 403
        assert "suspended" in blocked.json()["detail"]
    await as_operator.post(f"/api/company/nurseries/{world.nursery.id}/reactivate")
    assert (await as_admin.get("/api/admin/today")).status_code == 200


async def test_the_portals_do_not_cross(
    as_operator: AsyncClient, as_admin: AsyncClient, as_parent: AsyncClient
) -> None:
    assert (await as_operator.get("/api/admin/today")).status_code == 403
    assert (await as_operator.get("/api/parent/children")).status_code == 403
    assert (await as_admin.get("/api/company/nurseries")).status_code == 403
    assert (await as_parent.get("/api/company/overview")).status_code == 403


ENQUIRY = {
    "contact_name": "Sarah Jones",
    "nursery_name": "Bluebell Day Nursery",
    "email": "sarah@bluebell.example.com",
    "phone": "07700 900321",
    "region": "Yorkshire and the Humber",
    "children": "About 60",
    "interest": "pilot",
    "message": "We would like to try it in one room.",
}


async def test_an_enquiry_reaches_the_company_portal(
    anonymous: AsyncClient, as_operator: AsyncClient
) -> None:
    sent = await anonymous.post(
        "/api/public/enquiries", json=ENQUIRY, headers={"X-Requested-With": "fetch"}
    )
    assert sent.status_code == 201
    rows = (await as_operator.get("/api/company/enquiries")).json()
    assert [r["nursery_name"] for r in rows] == ["Bluebell Day Nursery"]
    assert rows[0]["region"] == "Yorkshire and the Humber"
    done = await as_operator.post(f"/api/company/enquiries/{rows[0]['id']}/handled")
    assert done.json()["handled_by"] == "ops@entraccess.example.com"


async def test_a_bot_is_thanked_and_ignored(
    anonymous: AsyncClient, as_operator: AsyncClient
) -> None:
    trapped = await anonymous.post(
        "/api/public/enquiries", json={**ENQUIRY, "website": "http://spam.example"}
    )
    assert trapped.status_code == 201
    assert (await as_operator.get("/api/company/enquiries")).json() == []


async def test_enquiries_are_rate_limited(anonymous: AsyncClient) -> None:
    codes = [
        (await anonymous.post("/api/public/enquiries", json=ENQUIRY)).status_code for _ in range(6)
    ]
    assert codes == [201] * 5 + [429]


async def test_nurseries_cannot_read_enquiries(as_admin: AsyncClient) -> None:
    assert (await as_admin.get("/api/company/enquiries")).status_code == 403
