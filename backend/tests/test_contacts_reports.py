"""Nursery contacts, sending a pass, the KPI summary and the evidence pack."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent
from app.notify import OUTBOX
from tests.conftest import World
from tests.test_collection import add_one_off, add_regular, pass_of
from tests.test_reconciliation import restrict

LONDON = ZoneInfo("Europe/London")
CONTACTS = (
    "Child,Contact name,Relationship,Phone,Password\n"
    "Maya Parent,Grace Hughes,Grandmother,07700 900111,bluebell\n"
    "maya parent,Tom Baker,Uncle,07700 900222,\n"
    "Leo Parent,Grace Hughes,Grandmother,07700 900111,\n"
)


async def add_contact(client: AsyncClient, child_id: object, name: str = "Grace Hughes") -> dict:
    response = await client.post(
        f"/api/admin/children/{child_id}/contacts",
        json={
            "collector_name": name,
            "collector_relationship": "Grandmother",
            "collector_phone": "07700 900111",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestNurseryContacts:
    async def test_a_contact_is_a_regular_collector_the_parents_see_and_hear_about(
        self, world: World, as_admin: AsyncClient, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        contact = await add_contact(as_admin, world.child.id)
        assert contact["source"] == "setting"
        assert contact["kind"] == "regular"
        assert contact["authorised_by_name"] == "Amira Admin"

        mine = (await as_parent.get(f"/api/parent/children/{world.child.id}/collectors")).json()
        assert [(c["collector_name"], c["source"]) for c in mine] == [("Grace Hughes", "setting")]
        assert sorted(m["To"] for m in OUTBOX.messages) == [
            "dad@acorns.example.com",
            "parent@acorns.example.com",
        ]
        assert "Grace Hughes (Grandmother) may collect Maya Parent" in str(
            OUTBOX.messages[0].get_content()
        )

        # It works at the door like any other collector.
        token = (await as_admin.get(f"/api/admin/collectors/{contact['id']}/pass")).json()["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        assert check["result"] == "valid"
        assert check["authorised_by_name"] == "Amira Admin"

    async def test_a_parent_can_remove_one(
        self, world: World, as_admin: AsyncClient, as_parent: AsyncClient
    ) -> None:
        contact = await add_contact(as_admin, world.child.id)
        removed = await as_parent.post(f"/api/parent/collectors/{contact['id']}/revoke")
        assert removed.json()["status"] == "revoked"

    async def test_not_twice_and_not_from_the_never_release_list(
        self, world: World, as_admin: AsyncClient
    ) -> None:
        await add_contact(as_admin, world.child.id)
        again = await as_admin.post(
            f"/api/admin/children/{world.child.id}/contacts",
            json={
                "collector_name": "grace  hughes",
                "collector_relationship": "Grandmother",
                "collector_phone": "07700 900111",
            },
        )
        assert again.status_code == 400
        assert "already a collector" in again.json()["detail"]

        await restrict(as_admin, world.sibling.id, "Rob Stranger")
        blocked = await as_admin.post(
            f"/api/admin/children/{world.sibling.id}/contacts",
            json={
                "collector_name": "Rob Stranger",
                "collector_relationship": "Uncle",
                "collector_phone": "07700 900333",
            },
        )
        assert blocked.status_code == 400
        assert "never-release" in blocked.json()["detail"]

    async def test_a_manager_cannot_send_a_parents_own_collector(
        self, world: World, as_admin: AsyncClient, as_parent: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        response = await as_admin.get(f"/api/admin/collectors/{auth['id']}/pass")
        assert response.status_code == 403

    async def test_import_adds_all_and_skips_what_is_there(
        self, world: World, as_admin: AsyncClient, as_parent: AsyncClient
    ) -> None:
        await add_regular(as_parent, world.child.id, collector_name="Tom Baker")
        result = await as_admin.post("/api/admin/contacts/import", json={"csv": CONTACTS})
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["added"] == 2
        assert body["skipped"] == 1
        leo = (await as_admin.get(f"/api/admin/children/{world.sibling.id}/collectors")).json()
        assert [c["collector_name"] for c in leo] == ["Grace Hughes"]
        maya = (await as_admin.get(f"/api/admin/children/{world.child.id}/collectors")).json()
        grace = next(c for c in maya if c["collector_name"] == "Grace Hughes")
        assert grace["note_for_staff"] == "bluebell"
        # One email per parent, listing everything added for their children.
        assert len([m for m in OUTBOX.messages if m["To"] == "parent@acorns.example.com"]) == 1

    async def test_import_is_all_or_nothing(self, world: World, as_admin: AsyncClient) -> None:
        bad = CONTACTS + "Ola Oak,Ann Smith,Aunt,07700 900444,\nZara Other,Bo,Aunt,07700 900555,\n"
        result = await as_admin.post("/api/admin/contacts/import", json={"csv": bad})
        assert result.status_code == 400
        detail = result.json()["detail"]
        assert "line 5: no child here called 'Ola Oak'" in detail
        assert "line 6: give the contact's full name" in detail
        assert (await as_admin.get(f"/api/admin/children/{world.child.id}/collectors")).json() == []

    async def test_missing_columns_are_named(self, as_admin: AsyncClient) -> None:
        result = await as_admin.post(
            "/api/admin/contacts/import", json={"csv": "Child,Name\nMaya Parent,Grace Hughes\n"}
        )
        assert result.status_code == 400
        assert "Contact name, Relationship, Phone" in result.json()["detail"]

    async def test_only_managers_add_contacts(self, as_staff: AsyncClient) -> None:
        response = await as_staff.post("/api/admin/contacts/import", json={"csv": CONTACTS})
        assert response.status_code == 403


class TestSendingAPass:
    async def test_the_pass_says_whose_it_is_and_the_sending_is_logged(
        self, world: World, as_parent: AsyncClient, session: AsyncSession
    ) -> None:
        auth = await add_one_off(as_parent, world.child.id)
        pass_ = await pass_of(as_parent, auth["id"])
        assert pass_["child_first_name"] == "Maya"
        assert pass_["nursery_name"] == "Little Acorns (demo)"
        sent = await as_parent.post(
            f"/api/parent/collectors/{auth['id']}/shared",
            json={"channel": "whatsapp", "what": "code"},
        )
        assert sent.status_code == 204
        event = await session.scalar(select(AuditEvent).where(AuditEvent.action == "pass.shared"))
        assert event is not None
        assert event.detail == "today's code for Nina Neighbour by WhatsApp"

    async def test_only_known_channels(self, world: World, as_parent: AsyncClient) -> None:
        auth = await add_one_off(as_parent, world.child.id)
        sent = await as_parent.post(
            f"/api/parent/collectors/{auth['id']}/shared",
            json={"channel": "carrier pigeon", "what": "link"},
        )
        assert sent.status_code == 422

    async def test_not_another_parents_collector(
        self, world: World, as_parent: AsyncClient, as_other_parent: AsyncClient
    ) -> None:
        auth = await add_one_off(as_parent, world.child.id)
        sent = await as_other_parent.post(
            f"/api/parent/collectors/{auth['id']}/shared",
            json={"channel": "sms", "what": "link"},
        )
        assert sent.status_code == 404


async def release(as_parent: AsyncClient, as_staff: AsyncClient, child_id: object) -> dict:
    auth = await add_regular(as_parent, child_id)
    token = (await pass_of(as_parent, auth["id"]))["token"]
    check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
    return (
        await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision",
            json={"release": True, "id_check_method": "photo_id"},
        )
    ).json()


class TestKpis:
    async def test_the_summary_counts_what_happened(
        self,
        world: World,
        as_parent: AsyncClient,
        as_staff: AsyncClient,
        as_admin: AsyncClient,
    ) -> None:
        await release(as_parent, as_staff, world.child.id)
        await as_staff.post(
            "/api/door/check/code", json={"child_id": str(world.sibling.id), "code": "000000"}
        )
        await add_contact(as_admin, world.sibling.id)
        await restrict(as_admin, world.unrelated_child.id, "Rob Stranger")

        k = (await as_admin.get("/api/admin/kpis")).json()
        assert k["releases"] == 1
        assert k["id_checks"] == {"photo_id": 1}
        assert k["blocked_by_result"] == {"wrong_code": 1}
        assert k["collectors_added_by_parents"] == 1
        assert k["contacts_added_by_nursery"] == 1
        assert k["restrictions_in_force"] == 1
        assert k["days_with_releases"] == 1
        assert k["days_without_register"] == 1

        today = datetime.now(LONDON).date().isoformat()
        await as_admin.post(
            "/api/admin/sign-outs/import",
            json={"day": today, "csv": "Child,Signed out\nZara Other,00:01\n"},
        )
        k = (await as_admin.get("/api/admin/kpis")).json()
        assert k["registers_imported"] == 1
        assert k["days_without_register"] == 0
        assert k["reconciliation_flags"]["no_handover"] == 1

    async def test_the_csv_reads_plainly(self, as_admin: AsyncClient) -> None:
        response = await as_admin.get("/api/admin/kpis.csv")
        assert response.status_code == 200
        assert "Children released at the door,0" in response.text

    async def test_a_period_is_at_most_a_quarter(self, as_admin: AsyncClient) -> None:
        today = datetime.now(LONDON).date()
        response = await as_admin.get(
            f"/api/admin/kpis?start={(today - timedelta(days=100)).isoformat()}"
            f"&end={today.isoformat()}"
        )
        assert response.status_code == 400


class TestEvidencePack:
    async def test_one_childs_pack_holds_their_story_and_nobody_elses(
        self,
        world: World,
        as_parent: AsyncClient,
        as_staff: AsyncClient,
        as_admin: AsyncClient,
    ) -> None:
        await release(as_parent, as_staff, world.child.id)
        await release(as_parent, as_staff, world.sibling.id)
        await restrict(as_admin, world.child.id, "Rob Stranger")

        pack = (await as_admin.get(f"/api/admin/evidence?child_id={world.child.id}")).json()
        assert pack["child_name"] == "Maya Parent"
        assert pack["generated_by"] == "Amira Admin"
        assert [c["collector_name"] for c in pack["collectors"]] == ["Grace Grandma"]
        assert [r["person_name"] for r in pack["restrictions"]] == ["Rob Stranger"]
        children = {e["child"] for e in pack["events"]}
        assert children == {"Maya Parent"}
        kinds = [e["kind"] for e in pack["events"]]
        assert "released" in kinds
        assert "restriction" in kinds
        assert pack["kpis"]["releases"] == 1

    async def test_the_whole_nursery_and_the_csv(
        self,
        world: World,
        as_parent: AsyncClient,
        as_staff: AsyncClient,
        as_admin: AsyncClient,
        session: AsyncSession,
    ) -> None:
        await release(as_parent, as_staff, world.child.id)
        await release(as_parent, as_staff, world.sibling.id)
        pack = (await as_admin.get("/api/admin/evidence")).json()
        assert pack["child_name"] is None
        assert pack["kpis"]["releases"] == 2

        response = await as_admin.get("/api/admin/evidence.csv")
        assert response.status_code == 200
        assert 'filename="evidence-all-' in response.headers["content-disposition"]
        lines = response.text.splitlines()
        assert lines[0] == "at_local,kind,child,detail,who"
        assert any("ID: photo id" in line for line in lines)
        logged = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "evidence.exported")
        )
        assert logged is not None

    async def test_not_another_nurserys_child(self, world: World, as_admin: AsyncClient) -> None:
        response = await as_admin.get(f"/api/admin/evidence?child_id={world.other_child.id}")
        assert response.status_code == 404

    async def test_room_leaders_cannot(self, as_staff: AsyncClient) -> None:
        assert (await as_staff.get("/api/admin/evidence")).status_code == 403
