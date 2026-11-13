"""The never-release list, how the ID check was made, and the sign-out reconciliation."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import names, reconcile
from app.collection import CollectionError
from app.models import (
    AuditEvent,
    Authorisation,
    CheckMethod,
    CheckResult,
    Child,
    CollectorKind,
    DoorCheck,
    Handover,
    HandoverOutcome,
    IdCheckMethod,
    Restriction,
    RestrictionReason,
)
from tests.conftest import World
from tests.test_collection import add_regular, pass_of

LONDON = ZoneInfo("Europe/London")


class TestNames:
    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("Grace Smith", "grace  smith"),
            ("Grace Smith", "Smith, Grace"),
            ("Grace Smith", "Grace A. Smith"),
            ("Zoë O'Brien", "Zoe OBrien"),
            ("Mark Jones", "Mark Peter Jones"),
        ],
    )
    def test_the_same_person(self, a: str, b: str) -> None:
        assert names.same_person(a, b)

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("Grace", "Grace Smith"),
            ("Grace Smith", "Grace Jones"),
            ("", "Grace Smith"),
            ("Mark Jones", "Mark Smith Peters"),
        ],
    )
    def test_different_people(self, a: str, b: str) -> None:
        assert not names.same_person(a, b)


async def restrict(client: AsyncClient, child_id: object, name: str = "Grace Grandma") -> dict:
    response = await client.post(
        f"/api/admin/children/{child_id}/restrictions",
        json={"person_name": name, "reason": "court_order", "reference": "ZW26P00123"},
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestTheNeverReleaseList:
    async def test_adding_one_removes_that_collector_at_once(
        self, world: World, as_parent: AsyncClient, as_admin: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]

        restriction = await restrict(as_admin, world.child.id, "grace grandma")
        assert restriction["removed_collectors"] == ["Grace Grandma"]
        assert restriction["created_by_name"] == "Amira Admin"

        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        assert check["result"] == "revoked"
        assert check["can_release"] is False
        # Staff see the list with every check for the child.
        assert check["restrictions"] == [{"person_name": "grace grandma", "reason": "court_order"}]

    async def test_it_does_not_touch_other_children(
        self, world: World, as_parent: AsyncClient, as_admin: AsyncClient
    ) -> None:
        sibling = await add_regular(as_parent, world.sibling.id)
        await restrict(as_admin, world.child.id)
        url = f"/api/admin/children/{world.sibling.id}/collectors"
        collectors = (await as_admin.get(url)).json()
        assert [c["status"] for c in collectors if c["id"] == sibling["id"]] == ["valid"]

    async def test_a_parent_cannot_add_them_back(
        self, world: World, as_parent: AsyncClient, as_admin: AsyncClient, session: AsyncSession
    ) -> None:
        await restrict(as_admin, world.child.id)
        response = await as_parent.post(
            f"/api/parent/children/{world.child.id}/collectors",
            json={
                "collector_name": "Grace  GRANDMA",
                "collector_relationship": "Grandparent",
                "collector_phone": "07700 900123",
                "kind": "regular",
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "speak to the nursery" in detail
        # The parent is not told why: that is for the nursery to explain.
        assert "court" not in detail.lower()
        blocked = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "authorisation.blocked")
        )
        assert blocked is not None

    async def test_the_door_refuses_even_a_collector_that_slipped_through(
        self,
        world: World,
        as_parent: AsyncClient,
        as_staff: AsyncClient,
        session: AsyncSession,
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        # Written straight to the table, so the collector is not removed.
        session.add(
            Restriction(
                nursery_id=world.nursery.id,
                child_id=world.child.id,
                person_name="Grace Grandma",
                reason=RestrictionReason.SAFEGUARDING,
                created_by_id=world.admin.id,
            )
        )
        await session.commit()
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        assert check["result"] == "restricted"
        assert "never-release list" in check["message"]

    async def test_one_added_while_the_collector_is_at_the_door_stops_the_release(
        self,
        world: World,
        as_parent: AsyncClient,
        as_staff: AsyncClient,
        session: AsyncSession,
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        assert check["result"] == "valid"
        session.add(
            Restriction(
                nursery_id=world.nursery.id,
                child_id=world.child.id,
                person_name="Grace Grandma",
                reason=RestrictionReason.COURT_ORDER,
                created_by_id=world.admin.id,
            )
        )
        await session.commit()
        response = await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision",
            json={"release": True, "id_check_method": "photo_id"},
        )
        assert response.status_code == 409
        assert "never-release" in response.json()["detail"]

    async def test_ending_it_keeps_the_record_and_lets_the_parent_add_them(
        self, world: World, as_parent: AsyncClient, as_admin: AsyncClient
    ) -> None:
        restriction = await restrict(as_admin, world.child.id)
        ended = await as_admin.post(f"/api/admin/restrictions/{restriction['id']}/end")
        assert ended.status_code == 200
        assert ended.json()["ended_at"] is not None
        listed = (await as_admin.get(f"/api/admin/children/{world.child.id}/restrictions")).json()
        assert [r["id"] for r in listed] == [restriction["id"]]
        await add_regular(as_parent, world.child.id)

    async def test_a_full_name_is_needed(self, world: World, as_admin: AsyncClient) -> None:
        response = await as_admin.post(
            f"/api/admin/children/{world.child.id}/restrictions",
            json={"person_name": "Grace", "reason": "other"},
        )
        assert response.status_code == 400

    async def test_only_managers_keep_the_list(
        self, world: World, as_staff: AsyncClient, as_parent: AsyncClient
    ) -> None:
        body = {"person_name": "Grace Grandma", "reason": "court_order"}
        for client in (as_staff, as_parent):
            response = await client.post(
                f"/api/admin/children/{world.child.id}/restrictions", json=body
            )
            assert response.status_code == 403

    async def test_not_for_another_nurserys_child(
        self, world: World, as_admin: AsyncClient
    ) -> None:
        response = await as_admin.post(
            f"/api/admin/children/{world.other_child.id}/restrictions",
            json={"person_name": "Grace Grandma", "reason": "court_order"},
        )
        assert response.status_code == 404


class TestHowTheIdWasChecked:
    async def test_the_method_is_kept(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        released = await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision",
            json={"release": True, "id_check_method": "known_to_staff"},
        )
        assert released.json()["id_check_method"] == "known_to_staff"

    async def test_the_password_needs_one_from_the_parent(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        bare = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, bare["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        url = f"/api/door/checks/{check['check_id']}/decision"
        refused = await as_staff.post(url, json={"release": True, "id_check_method": "password"})
        assert refused.status_code == 400
        assert "did not set a password" in refused.json()["detail"]

        with_word = await add_regular(
            as_parent,
            world.sibling.id,
            collector_name="Nina Neighbour",
            note_for_staff="Password: bluebell",
        )
        token = (await pass_of(as_parent, with_word["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        released = await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision",
            json={"release": True, "id_check_method": "password"},
        )
        assert released.status_code == 200

    async def test_a_refusal_keeps_no_method(
        self, world: World, as_parent: AsyncClient, as_staff: AsyncClient
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        token = (await pass_of(as_parent, auth["id"]))["token"]
        check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
        refused = await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision",
            json={
                "release": False,
                "reason": "Name on ID did not match",
                "id_check_method": "photo_id",
            },
        )
        assert refused.json()["id_check_method"] is None


# Reconciliation runs on a past day, so the times are fixed and nothing depends
# on when the tests run.
DAY = datetime.now(LONDON).date() - timedelta(days=2)


def at(hour: int, minute: int) -> datetime:
    return datetime.combine(DAY, time(hour, minute), tzinfo=LONDON).astimezone(UTC)


async def handover(
    session: AsyncSession,
    world: World,
    child: Child,
    collector: str,
    when: datetime,
    *,
    released: bool = True,
) -> None:
    auth = Authorisation(
        nursery_id=world.nursery.id,
        child_id=child.id,
        authorised_by_id=world.parent.id,
        collector_name=collector,
        collector_relationship="Grandparent",
        collector_phone="07700 900123",
        kind=CollectorKind.REGULAR,
        valid_from=when - timedelta(days=7),
    )
    session.add(auth)
    await session.flush()
    check = DoorCheck(
        nursery_id=world.nursery.id,
        checked_by_id=world.staff.id,
        method=CheckMethod.PASS,
        result=CheckResult.VALID,
        child_id=child.id,
        authorisation_id=auth.id,
        checked_at=when,
    )
    session.add(check)
    await session.flush()
    session.add(
        Handover(
            nursery_id=world.nursery.id,
            door_check_id=check.id,
            child_id=child.id,
            authorisation_id=auth.id,
            outcome=HandoverOutcome.RELEASED if released else HandoverOutcome.REFUSED,
            refusal_reason=None if released else "No photo ID",
            child_name=child.full_name,
            collector_name=collector,
            collector_relationship="Grandparent",
            authorised_by_name="Priya Parent",
            staff_id=world.staff.id,
            staff_name="Sam Staff",
            id_checked=released,
            id_check_method=IdCheckMethod.PHOTO_ID if released else None,
            occurred_at=when,
        )
    )
    await session.commit()


async def upload(client: AsyncClient, text: str, day: date = DAY) -> dict:
    response = await client.post(
        "/api/admin/sign-outs/import",
        json={"day": day.isoformat(), "csv": text, "source": "famly.csv"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def day_of(client: AsyncClient, day: date = DAY) -> dict:
    response = await client.get(f"/api/admin/reconciliation?day={day.isoformat()}")
    assert response.status_code == 200, response.text
    return response.json()


def by_child(result: dict) -> dict[str, list[str]]:
    return {line["child_name"]: line["flags"] for line in result["lines"]}


class TestReadingARegister:
    def test_first_name_and_surname_columns_and_a_twelve_hour_clock(self) -> None:
        rows = reconcile.parse(
            "First name;Surname;Time out;Collected by\nMaya;Parent;3:42 pm;Grace\n", DAY
        )
        assert [(r.child_name, r.clock, r.collected_by) for r in rows] == [
            ("Maya Parent", time(15, 42), "Grace")
        ]

    def test_children_with_no_time_have_not_left(self) -> None:
        rows = reconcile.parse("Child,Signed out\nMaya Parent,\nLeo Parent,16:05\n", DAY)
        assert [r.child_name for r in rows] == ["Leo Parent"]

    def test_a_time_with_the_date_in_it(self) -> None:
        rows = reconcile.parse(f"Child,Signed out\nLeo Parent,{DAY:%d/%m/%Y} 16:05\n", DAY)
        assert rows[0].clock == time(16, 5)

    def test_rows_from_another_day_stop_the_import(self) -> None:
        other = DAY - timedelta(days=1)
        with pytest.raises(CollectionError, match="line 2"):
            reconcile.parse(f"Child,Date,Signed out\nLeo Parent,{other.isoformat()},16:05\n", DAY)

    def test_an_unreadable_time_stops_the_import(self) -> None:
        with pytest.raises(CollectionError, match="cannot read the time 'teatime'"):
            reconcile.parse("Child,Signed out\nLeo Parent,teatime\n", DAY)

    def test_missing_columns_are_named(self) -> None:
        with pytest.raises(CollectionError, match="child's name"):
            reconcile.parse("Kid,Signed out\nLeo,16:05\n", DAY)
        with pytest.raises(CollectionError, match="sign-out time"):
            reconcile.parse("Child,Room\nLeo Parent,Caterpillars\n", DAY)


class TestReconciliation:
    async def test_every_kind_of_disagreement_is_flagged(
        self, world: World, as_admin: AsyncClient, session: AsyncSession
    ) -> None:
        await handover(session, world, world.child, "Grace Grandma", at(15, 30))
        await handover(session, world, world.sibling, "Grace Grandma", at(15, 31))
        # Zara was refused once, then left with nobody checked at the door.
        await handover(
            session, world, world.unrelated_child, "Rob Stranger", at(15, 0), released=False
        )

        imported = await upload(
            as_admin,
            "Child,Signed out,Collected by\n"
            "Maya Parent,16:10,Dev Parent\n"  # someone else, 40 minutes later
            "Zara Other,15:45,Aunt\n"  # never released at the door
            "Nobody Here,15:50,\n"  # not one of ours
            "Zara Other,15:46,\n",  # twice
        )
        assert imported["rows"] == 4
        assert imported["imported_by_name"] == "Amira Admin"

        result = await day_of(as_admin)
        flags = by_child(result)
        assert flags["Maya Parent"] == ["collector_mismatch", "time_gap"]
        assert flags["Leo Parent"] == ["no_sign_out"]
        assert flags["Zara Other"] == ["no_handover", "signed_out_twice"]
        assert flags["Nobody Here"] == ["unknown_child"]
        assert result["flagged"] == 4
        zara = next(line for line in result["lines"] if line["child_name"] == "Zara Other")
        assert zara["refusals"] == ["15:00 Rob Stranger: No photo ID"]

    async def test_a_matching_day_has_no_flags(
        self, world: World, as_admin: AsyncClient, session: AsyncSession
    ) -> None:
        await handover(session, world, world.child, "Grace Grandma", at(15, 30))
        await handover(session, world, world.sibling, "Grace Grandma", at(15, 31))
        await upload(
            as_admin,
            # First name only, the relationship word, and a few minutes either way.
            "Child,Signed out,Collected by\n"
            "maya parent,15:36,Grace\n"
            "Leo Parent,15:25,Grandparent\n",
        )
        result = await day_of(as_admin)
        assert by_child(result) == {"Maya Parent": [], "Leo Parent": []}
        assert result["matched"] == 2
        maya = next(line for line in result["lines"] if line["child_name"] == "Maya Parent")
        assert maya["id_check_method"] == "photo_id"
        assert maya["staff_name"] == "Sam Staff"

    async def test_before_an_import_only_the_door_side_shows(
        self, world: World, as_admin: AsyncClient, session: AsyncSession
    ) -> None:
        await handover(session, world, world.child, "Grace Grandma", at(15, 30))
        result = await day_of(as_admin)
        assert result["register_import"] is None
        assert by_child(result) == {"Maya Parent": []}

    async def test_the_latest_import_is_the_one_used(
        self, world: World, as_admin: AsyncClient, session: AsyncSession
    ) -> None:
        await handover(session, world, world.child, "Grace Grandma", at(15, 30))
        await upload(as_admin, "Child,Signed out\nZara Other,15:00\n")
        await upload(as_admin, "Child,Signed out\nMaya Parent,15:30\n")
        assert by_child(await day_of(as_admin)) == {"Maya Parent": []}

    async def test_a_name_shared_by_two_children_is_not_guessed(
        self, world: World, as_admin: AsyncClient, session: AsyncSession
    ) -> None:
        session.add(Child(nursery_id=world.nursery.id, full_name="Maya Parent", room="Ladybirds"))
        await session.commit()
        await upload(as_admin, "Child,Signed out\nMaya Parent,15:30\n")
        assert by_child(await day_of(as_admin)) == {"Maya Parent": ["unknown_child"]}

    async def test_the_export_reads_plainly_and_is_logged(self, as_admin: AsyncClient) -> None:
        await upload(as_admin, "Child,Signed out,Collected by\nZara Other,15:45,=HYPERLINK()\n")
        response = await as_admin.get(f"/api/admin/reconciliation.csv?day={DAY.isoformat()}")
        assert response.status_code == 200
        lines = response.text.splitlines()
        assert "Signed out, but not released at the door" in lines[1]
        assert "'=HYPERLINK()" in lines[1]
        activity = (await as_admin.get("/api/admin/activity")).json()
        assert any(a["what"].startswith("Imported the sign-out register") for a in activity)
        assert any(a["what"].startswith("Exported a reconciliation") for a in activity)

    async def test_a_day_that_has_not_happened(self, as_admin: AsyncClient) -> None:
        tomorrow = datetime.now(LONDON).date() + timedelta(days=1)
        response = await as_admin.post(
            "/api/admin/sign-outs/import",
            json={"day": tomorrow.isoformat(), "csv": "Child,Signed out\nMaya Parent,15:30\n"},
        )
        assert response.status_code == 400

    async def test_room_leaders_and_parents_cannot_see_it(
        self, as_staff: AsyncClient, as_parent: AsyncClient
    ) -> None:
        for client in (as_staff, as_parent):
            assert (await client.get("/api/admin/reconciliation")).status_code == 403

    async def test_another_nurserys_register_is_not_ours(
        self, world: World, as_admin: AsyncClient
    ) -> None:
        # Ola is at the other nursery: her name means nothing here.
        await upload(as_admin, "Child,Signed out\nOla Oak,15:30\n")
        assert by_child(await day_of(as_admin)) == {"Ola Oak": ["unknown_child"]}
        assert world.other_child.id != uuid.UUID(int=0)
