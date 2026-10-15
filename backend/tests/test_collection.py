"""The journey that is the product: a parent authorises, staff check, a child goes home."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, DoorCheck, Handover
from app.notify import OUTBOX
from tests.conftest import World

LONDON = ZoneInfo("Europe/London")


def today() -> str:
    return datetime.now(LONDON).date().isoformat()


async def add_regular(client: AsyncClient, child_id: object, **extra: object) -> dict:
    body = {
        "collector_name": "Grace Grandma",
        "collector_relationship": "Grandparent",
        "collector_phone": "07700 900123",
        "kind": "regular",
        **extra,
    }
    response = await client.post(f"/api/parent/children/{child_id}/collectors", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def add_one_off(client: AsyncClient, child_id: object) -> dict:
    body = {
        "collector_name": "Nina Neighbour",
        "collector_relationship": "Neighbour",
        "collector_phone": "07700 900456",
        "kind": "one_off",
        "on_date": today(),
    }
    response = await client.post(f"/api/parent/children/{child_id}/collectors", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def pass_of(client: AsyncClient, auth_id: str) -> dict:
    response = await client.get(f"/api/parent/collectors/{auth_id}/pass")
    assert response.status_code == 200
    return response.json()


class TestTheWholeJourney:
    async def test_authorise_check_release_and_tell_both_parents(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient, session: AsyncSession
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        assert auth["status"] == "valid"
        pass_ = await pass_of(as_parent, auth["id"])
        assert pass_["token"].startswith("CP1.")
        assert len(pass_["code_today"]) == 6

        check = (await as_staff.post("/api/door/check/pass", json={"token": pass_["token"]})).json()
        assert check["result"] == "valid"
        assert check["can_release"] is True
        assert check["child_name"] == "Maya Parent"
        assert check["collector_name"] == "Grace Grandma"
        assert check["authorised_by_name"] == "Priya Parent"

        decision = await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision", json={"release": True}
        )
        assert decision.status_code == 200, decision.text
        handover = decision.json()
        assert handover["outcome"] == "released"
        assert handover["staff_name"] == "Sam Staff"

        # Both parents linked to the child hear about it, not only the one who
        # authorised the collector.
        assert sorted(m["To"] for m in OUTBOX.messages) == [
            "dad@acorns.example.com",
            "parent@acorns.example.com",
        ]
        assert "has been collected" in OUTBOX.messages[0]["Subject"]

        history = (await as_parent.get("/api/parent/handovers")).json()
        assert [h["collector_name"] for h in history] == ["Grace Grandma"]
        audits = await session.scalar(select(func.count()).select_from(AuditEvent))
        assert audits and audits >= 1

    async def test_the_daily_code_works_against_the_child(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        code = (await pass_of(as_parent, auth["id"]))["code_today"]
        check = (
            await as_staff.post(
                "/api/door/check/code", json={"child_id": str(world.child.id), "code": code}
            )
        ).json()
        assert check["result"] == "valid"
        assert check["method"] == "code"

    async def test_the_code_does_not_work_against_another_child(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        code = (await pass_of(as_parent, auth["id"]))["code_today"]
        check = (
            await as_staff.post(
                "/api/door/check/code",
                json={"child_id": str(world.unrelated_child.id), "code": code},
            )
        ).json()
        assert check["result"] == "wrong_code"
        assert check["can_release"] is False

    async def test_a_refusal_needs_a_reason_and_tells_the_parents(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        no_reason = await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision", json={"release": False}
        )
        assert no_reason.status_code == 400
        refused = await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision",
            json={"release": False, "reason": "No photo ID"},
        )
        assert refused.json()["outcome"] == "refused"
        assert "was not released" in OUTBOX.messages[0]["Subject"]

    async def test_a_check_can_only_be_decided_once(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        url = f"/api/door/checks/{check['check_id']}/decision"
        assert (await as_staff.post(url, json={"release": True})).status_code == 200
        assert (await as_staff.post(url, json={"release": True})).status_code == 409


class TestRevocationAndReissue:
    async def test_revoking_stops_the_pass_at_once(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        revoked = await as_parent.post(f"/api/parent/collectors/{auth['id']}/revoke")
        assert revoked.json()["status"] == "revoked"
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        assert check["result"] == "revoked"
        assert check["can_release"] is False

    async def test_revoked_while_at_the_door_is_not_released(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        assert check["result"] == "valid"
        await as_parent.post(f"/api/parent/collectors/{auth['id']}/revoke")
        decision = await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision", json={"release": True}
        )
        assert decision.status_code == 409

    async def test_reissue_retires_the_old_pass_and_code(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        old = await pass_of(as_parent, auth["id"])
        new = (await as_parent.post(f"/api/parent/collectors/{auth['id']}/reissue")).json()
        assert new["token"] != old["token"]
        stale = (await as_staff.post("/api/door/check/pass", json={"token": old["token"]})).json()
        assert stale["result"] == "reissued"
        fresh = (await as_staff.post("/api/door/check/pass", json={"token": new["token"]})).json()
        assert fresh["result"] == "valid"

    async def test_a_child_leaving_revokes_every_collector(
        self, world: World, as_parent: AsyncClient, as_admin: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        assert (
            await as_admin.post(f"/api/admin/children/{world.child.id}/leave")
        ).status_code == 200
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        assert check["result"] == "revoked"


class TestOneOffCollectors:
    async def test_a_one_off_pass_works_once(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_one_off(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        first = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        await as_staff.post(
            f"/api/door/checks/{first['check_id']}/decision", json={"release": True}
        )
        second = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        assert second["result"] == "already_used"

    async def test_one_off_dates_are_limited(self, world: World, as_parent: AsyncClient) -> None:
        far = (datetime.now(LONDON).date() + timedelta(days=30)).isoformat()
        past = (datetime.now(LONDON).date() - timedelta(days=1)).isoformat()
        for day in (far, past):
            response = await as_parent.post(
                f"/api/parent/children/{world.child.id}/collectors",
                json={
                    "collector_name": "Nina Neighbour",
                    "collector_relationship": "Neighbour",
                    "collector_phone": "07700 900456",
                    "kind": "one_off",
                    "on_date": day,
                },
            )
            assert response.status_code == 400

    async def test_a_future_regular_collector_is_not_yet_valid(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        tomorrow = (datetime.now(LONDON).date() + timedelta(days=1)).isoformat()
        auth = await add_regular(as_parent, world.child.id, start_date=tomorrow)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        assert check["result"] == "not_yet_valid"


class TestAtTheDoor:
    async def test_rubbish_is_unreadable_and_recorded(
        self, as_staff: AsyncClient, session: AsyncSession
    ) -> None:
        check = (await as_staff.post("/api/door/check/pass", json={"token": "hello"})).json()
        assert check["result"] == "unreadable"
        recorded = await session.scalar(select(func.count()).select_from(DoorCheck))
        assert recorded == 1

    async def test_a_forged_pass_is_refused(self, as_staff: AsyncClient) -> None:
        forged = "CP1.AAAAAAAAAAAAAAAAAAAAAAAAAAA.AAAAAAAAAAAAAAAAAAAAAA"
        check = (await as_staff.post("/api/door/check/pass", json={"token": forged})).json()
        assert check["result"] in {"wrong_nursery", "unreadable"}
        assert check["can_release"] is False

    async def test_wrong_codes_pause_code_entry_for_that_child(
        self, world: World, as_staff: AsyncClient
    ) -> None:
        results = []
        for _ in range(6):
            check = (
                await as_staff.post(
                    "/api/door/check/code",
                    json={"child_id": str(world.child.id), "code": "000000"},
                )
            ).json()
            results.append(check["result"])
        assert results[:5] == ["wrong_code"] * 5
        assert results[5] == "locked"

    async def test_an_invalid_check_cannot_be_released(self, as_staff: AsyncClient) -> None:
        check = (await as_staff.post("/api/door/check/pass", json={"token": "nope"})).json()
        decision = await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision", json={"release": True}
        )
        assert decision.status_code == 409

    async def test_parents_cannot_use_the_door(self, as_parent: AsyncClient) -> None:
        response = await as_parent.post("/api/door/check/pass", json={"token": "x"})
        assert response.status_code == 403


class TestNurseriesAreSeparate:
    async def test_a_pass_from_one_nursery_fails_at_another(
        self, world: World, as_parent: AsyncClient, as_other_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        check = (await as_other_staff.post("/api/door/check/pass", json={"token": token})).json()
        assert check["result"] == "wrong_nursery"

    async def test_a_parent_cannot_authorise_for_a_child_not_theirs(
        self, world: World, as_parent: AsyncClient, as_other_parent: AsyncClient
    ) -> None:
        for client, child in (
            (as_parent, world.unrelated_child.id),
            (as_parent, world.other_child.id),
            (as_other_parent, world.child.id),
        ):
            response = await client.post(
                f"/api/parent/children/{child}/collectors",
                json={
                    "collector_name": "Someone Else",
                    "collector_relationship": "Friend",
                    "collector_phone": "07700 900999",
                    "kind": "regular",
                },
            )
            assert response.status_code == 404

    async def test_a_parent_cannot_see_or_revoke_another_familys_collector(
        self, world: World, as_parent: AsyncClient, as_other_parent: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        assert (
            await as_other_parent.get(f"/api/parent/collectors/{auth['id']}/pass")
        ).status_code == 404
        assert (
            await as_other_parent.post(f"/api/parent/collectors/{auth['id']}/revoke")
        ).status_code == 404

    async def test_staff_cannot_check_codes_for_another_nurserys_child(
        self, world: World, as_other_staff: AsyncClient
    ) -> None:
        response = await as_other_staff.post(
            "/api/door/check/code", json={"child_id": str(world.child.id), "code": "123456"}
        )
        assert response.status_code == 404


class TestTheRecord:
    async def test_admin_sees_handovers_exceptions_and_exports_safely(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient, as_admin: AsyncClient
    ) -> None:
        auth = await add_regular(
            as_parent, world.child.id, collector_name="=HYPERLINK(1)", collector_relationship="Aunt"
        )
        token = (await pass_of(as_parent, auth["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision", json={"release": True}
        )
        await as_staff.post("/api/door/check/pass", json={"token": "junk"})

        today_ = (await as_admin.get("/api/admin/today")).json()
        assert today_["released"] == 1
        assert today_["exceptions"] == 1

        exceptions = (await as_admin.get("/api/admin/checks")).json()
        assert [e["result"] for e in exceptions] == ["unreadable"]

        csv = await as_admin.get("/api/admin/handovers.csv")
        assert csv.status_code == 200
        assert "'=HYPERLINK(1)" in csv.text, "a formula must not reach a spreadsheet as a formula"

    async def test_staff_cannot_reach_admin(self, as_staff: AsyncClient) -> None:
        assert (await as_staff.get("/api/admin/today")).status_code == 403

    async def test_handovers_are_never_edited(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient, session: AsyncSession
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision", json={"release": True}
        )
        # Revoking afterwards leaves the record of who collected exactly as it was.
        await as_parent.post(f"/api/parent/collectors/{auth['id']}/revoke")
        row = await session.scalar(select(Handover))
        assert row is not None
        assert row.collector_name == "Grace Grandma"
        assert row.occurred_at.tzinfo is not None, "times come back in UTC, never naive"
        assert row.occurred_at <= datetime.now(UTC)


class TestThePublicPassPage:
    async def test_the_collector_sees_a_first_name_only(
        self, world: World, as_parent: AsyncClient, anonymous: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        page = await anonymous.get(f"/api/public/pass/{token}")
        assert page.status_code == 200
        body = page.json()
        assert body["child_first_name"] == "Maya"
        assert "Parent" not in body["child_first_name"]
        assert body["status"] == "valid"

    async def test_a_tampered_link_is_not_found(self, anonymous: AsyncClient) -> None:
        assert (await anonymous.get("/api/public/pass/CP1.xxx.yyy")).status_code == 404


class TestSigningIn:
    async def test_wrong_password_and_unknown_email_look_the_same(
        self, world: World, anonymous: AsyncClient
    ) -> None:
        a = await anonymous.post(
            "/api/auth/sign-in", json={"email": world.parent.email, "password": "wrong"}
        )
        b = await anonymous.post(
            "/api/auth/sign-in", json={"email": "nobody@acorns.example.com", "password": "wrong"}
        )
        assert a.status_code == b.status_code == 401
        assert a.json() == b.json()

    async def test_a_change_without_the_header_is_refused(self, as_parent: AsyncClient) -> None:
        response = await as_parent.post(
            "/api/auth/sign-out", headers={"X-Requested-With": "something-else"}
        )
        assert response.status_code == 403

    async def test_repeated_failures_are_slowed_down(
        self, world: World, anonymous: AsyncClient
    ) -> None:
        codes = [
            (
                await anonymous.post(
                    "/api/auth/sign-in", json={"email": world.staff.email, "password": "wrong"}
                )
            ).status_code
            for _ in range(11)
        ]
        assert codes[:10] == [401] * 10
        assert codes[10] == 429

    async def test_signed_out_requests_are_refused(self, anonymous: AsyncClient) -> None:
        assert (await anonymous.get("/api/parent/children")).status_code == 401


class TestDeploymentSettings:
    def test_staging_refuses_the_development_keys(self) -> None:
        import pytest
        from pydantic import ValidationError

        from app.config import Settings

        with pytest.raises(ValidationError):
            Settings(ENVIRONMENT="staging")
        ok = Settings(ENVIRONMENT="staging", SECRET_KEY="s" * 40, PASS_SIGNING_KEY="p" * 40)
        assert ok.secure_cookies is True
