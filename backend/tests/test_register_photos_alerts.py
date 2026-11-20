"""Collector photos, the arrival register (online and offline) and non-arrival alerts."""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import alerts, db, photos
from app.models import Arrival, Child, CollectorPhoto, Nursery
from app.notify import OUTBOX
from tests.conftest import World
from tests.test_collection import add_one_off, add_regular, pass_of

LONDON = ZoneInfo("Europe/London")
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def data_url(raw: bytes, kind: str = "image/jpeg") -> str:
    return f"data:{kind};base64,{base64.b64encode(raw).decode()}"


def today() -> str:
    return datetime.now(LONDON).date().isoformat()


async def every_day(*children: Child) -> None:
    async with db.sessionmaker()() as s:
        for child in children:
            row = await s.get(Child, child.id)
            assert row is not None
            row.session_days = "1234567"
        await s.commit()


async def valid_check(as_staff: AsyncClient, token: str) -> dict:
    check = (await as_staff.post("/api/door/check/pass", json={"token": token})).json()
    assert check["result"] == "valid", check
    return check


class TestCollectorPhotos:
    async def test_a_parent_adds_a_photo_and_the_door_shows_it(
        self, as_parent: AsyncClient, as_staff: AsyncClient, world: World
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        assert auth["has_photo"] is False
        put = await as_parent.put(
            f"/api/parent/collectors/{auth['id']}/photo", json={"data_url": data_url(JPEG)}
        )
        assert put.status_code == 204, put.text
        listed = (await as_parent.get(f"/api/parent/children/{world.child.id}/collectors")).json()
        assert listed[0]["has_photo"] is True
        mine = await as_parent.get(f"/api/parent/collectors/{auth['id']}/photo")
        assert mine.status_code == 200 and mine.content == JPEG

        check = await valid_check(as_staff, (await pass_of(as_parent, auth["id"]))["token"])
        assert check["has_photo"] is True
        shown = await as_staff.get(f"/api/door/checks/{check['check_id']}/photo")
        assert shown.status_code == 200
        assert shown.headers["content-type"] == "image/jpeg"
        assert shown.content == JPEG

    async def test_the_photo_is_only_shown_for_a_valid_check_at_this_nursery(
        self,
        as_parent: AsyncClient,
        as_staff: AsyncClient,
        as_other_staff: AsyncClient,
        world: World,
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        await as_parent.put(
            f"/api/parent/collectors/{auth['id']}/photo",
            json={"data_url": data_url(PNG, "image/png")},
        )
        check = await valid_check(as_staff, (await pass_of(as_parent, auth["id"]))["token"])
        elsewhere = await as_other_staff.get(f"/api/door/checks/{check['check_id']}/photo")
        assert elsewhere.status_code == 404
        refused = (await as_staff.post("/api/door/check/pass", json={"token": "nonsense"})).json()
        assert (
            await as_staff.get(f"/api/door/checks/{refused['check_id']}/photo")
        ).status_code == 404
        # A parent cannot use the door's route at all.
        assert (
            await as_parent.get(f"/api/door/checks/{check['check_id']}/photo")
        ).status_code == 403

    async def test_only_a_small_real_image_is_accepted(
        self, as_parent: AsyncClient, world: World
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        url = f"/api/parent/collectors/{auth['id']}/photo"
        not_image = await as_parent.put(url, json={"data_url": data_url(b"<svg>" + b"x" * 100)})
        assert not_image.status_code == 400
        assert "JPEG" in not_image.json()["detail"]
        lying = await as_parent.put(url, json={"data_url": data_url(b"GIF89a" + b"0" * 100)})
        assert lying.status_code == 400
        huge = await as_parent.put(
            url, json={"data_url": data_url(JPEG + b"\x00" * (photos.MAX_BYTES + 1))}
        )
        assert huge.status_code in (400, 422)
        garbage = await as_parent.put(url, json={"data_url": "data:image/jpeg;base64,%%%%not"})
        assert garbage.status_code == 400

    async def test_another_family_cannot_see_or_set_the_photo(
        self, as_parent: AsyncClient, as_other_parent: AsyncClient, world: World
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        await as_parent.put(
            f"/api/parent/collectors/{auth['id']}/photo", json={"data_url": data_url(JPEG)}
        )
        url = f"/api/parent/collectors/{auth['id']}/photo"
        assert (await as_other_parent.get(url)).status_code == 404
        assert (
            await as_other_parent.put(url, json={"data_url": data_url(JPEG)})
        ).status_code == 404

    async def test_removing_the_collector_deletes_the_photo(
        self, as_parent: AsyncClient, session: AsyncSession, world: World
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        await as_parent.put(
            f"/api/parent/collectors/{auth['id']}/photo", json={"data_url": data_url(JPEG)}
        )
        await as_parent.post(f"/api/parent/collectors/{auth['id']}/revoke")
        assert await session.scalar(select(func.count()).select_from(CollectorPhoto)) == 0

    async def test_a_one_off_collection_happening_deletes_the_photo(
        self, as_parent: AsyncClient, as_staff: AsyncClient, session: AsyncSession, world: World
    ) -> None:
        auth = await add_one_off(as_parent, world.child.id)
        await as_parent.put(
            f"/api/parent/collectors/{auth['id']}/photo", json={"data_url": data_url(JPEG)}
        )
        check = await valid_check(as_staff, (await pass_of(as_parent, auth["id"]))["token"])
        decided = await as_staff.post(
            f"/api/door/checks/{check['check_id']}/decision",
            json={"release": True, "id_check_method": "photo_id"},
        )
        assert decided.status_code == 200, decided.text
        assert await session.scalar(select(func.count()).select_from(CollectorPhoto)) == 0

    async def test_housekeeping_clears_photos_of_ended_authorisations(
        self, as_parent: AsyncClient, world: World
    ) -> None:
        auth = await add_regular(as_parent, world.child.id)
        await as_parent.put(
            f"/api/parent/collectors/{auth['id']}/photo", json={"data_url": data_url(JPEG)}
        )
        async with db.sessionmaker()() as s:
            assert await photos.purge_unneeded(s, datetime.now(UTC)) == 0
            # A week from now the open-ended collector is still current...
            assert await photos.purge_unneeded(s, datetime.now(UTC) + timedelta(days=7)) == 0
        dated = await add_regular(
            as_parent,
            world.child.id,
            collector_name="Dated Collector",
            end_date=today(),
        )
        await as_parent.put(
            f"/api/parent/collectors/{dated['id']}/photo", json={"data_url": data_url(JPEG)}
        )
        async with db.sessionmaker()() as s:
            # ...and the one whose last day was today is gone once it ends.
            assert await photos.purge_unneeded(s, datetime.now(UTC) + timedelta(days=2)) == 1
            await s.commit()
            assert await s.get(CollectorPhoto, uuid.UUID(dated["id"])) is None


class TestTheRegister:
    async def test_staff_mark_a_child_in_once_a_day(
        self, as_staff: AsyncClient, world: World
    ) -> None:
        first = await as_staff.post(
            "/api/door/register/arrivals", json={"child_id": str(world.child.id)}
        )
        assert first.status_code == 200, first.text
        assert first.json()["arrived_at"] is not None
        again = await as_staff.post(
            "/api/door/register/arrivals", json={"child_id": str(world.child.id)}
        )
        assert again.json()["arrived_at"] == first.json()["arrived_at"]
        rows = {
            r["full_name"]: r for r in (await as_staff.get("/api/door/register")).json()["children"]
        }
        assert rows["Maya Parent"]["arrived_at"] is not None
        assert rows["Leo Parent"]["arrived_at"] is None

    async def test_a_mistaken_mark_can_be_undone_and_is_logged(
        self, as_staff: AsyncClient, as_admin: AsyncClient, world: World
    ) -> None:
        await as_staff.post("/api/door/register/arrivals", json={"child_id": str(world.child.id)})
        undone = await as_staff.delete(f"/api/door/register/arrivals/{world.child.id}")
        assert undone.status_code == 204
        rows = {
            r["full_name"]: r for r in (await as_staff.get("/api/door/register")).json()["children"]
        }
        assert rows["Maya Parent"]["arrived_at"] is None
        log = (await as_admin.get(f"/api/admin/activity?start={today()}&end={today()}")).json()
        assert any("arrival.undone" in e["what"] or "Maya" in e["what"] for e in log)

    async def test_parents_and_other_nurseries_cannot_use_the_register(
        self, as_parent: AsyncClient, as_other_staff: AsyncClient, world: World
    ) -> None:
        assert (await as_parent.get("/api/door/register")).status_code == 403
        theirs = await as_other_staff.post(
            "/api/door/register/arrivals", json={"child_id": str(world.child.id)}
        )
        assert theirs.status_code == 404


class TestOfflineMarks:
    async def test_a_mark_made_offline_is_recorded_at_the_time_it_was_made(
        self, as_staff: AsyncClient, session: AsyncSession, world: World
    ) -> None:
        made = datetime.now(UTC) - timedelta(minutes=40)
        sent = await as_staff.post(
            "/api/door/register/sync",
            json={
                "marks": [
                    {
                        "child_id": str(world.child.id),
                        "occurred_at": made.isoformat(),
                        "client_id": "phone-mark-0001",
                    }
                ]
            },
        )
        assert sent.json()["results"][0]["status"] == "recorded"
        arrival = await session.scalar(select(Arrival).where(Arrival.child_id == world.child.id))
        assert arrival is not None
        assert abs((arrival.arrived_at - made).total_seconds()) < 1
        assert arrival.recorded_offline is True

    async def test_sending_the_same_mark_twice_records_it_once(
        self, as_staff: AsyncClient, session: AsyncSession, world: World
    ) -> None:
        mark = {
            "child_id": str(world.child.id),
            "occurred_at": datetime.now(UTC).isoformat(),
            "client_id": "phone-mark-0002",
        }
        await as_staff.post("/api/door/register/sync", json={"marks": [mark]})
        again = await as_staff.post("/api/door/register/sync", json={"marks": [mark]})
        assert again.json()["results"][0]["status"] == "duplicate"
        assert await session.scalar(select(func.count()).select_from(Arrival)) == 1

    async def test_a_refused_mark_does_not_stop_the_rest(
        self, as_staff: AsyncClient, world: World
    ) -> None:
        now = datetime.now(UTC)
        marks = [
            {
                "child_id": str(world.child.id),
                "occurred_at": (now + timedelta(hours=2)).isoformat(),
                "client_id": "phone-future-1",
            },
            {
                "child_id": str(world.sibling.id),
                "occurred_at": (now - timedelta(days=3)).isoformat(),
                "client_id": "phone-old-0001",
            },
            {
                "child_id": str(world.other_child.id),
                "occurred_at": now.isoformat(),
                "client_id": "phone-other-01",
            },
            {
                "child_id": str(world.unrelated_child.id),
                "occurred_at": now.isoformat(),
                "client_id": "phone-good-001",
            },
        ]
        results = (await as_staff.post("/api/door/register/sync", json={"marks": marks})).json()[
            "results"
        ]
        assert [r["status"] for r in results] == ["rejected", "rejected", "rejected", "recorded"]
        assert "future" in results[0]["message"]
        assert "too old" in results[1]["message"]

    async def test_a_child_marked_in_by_a_colleague_is_already_in(
        self, as_staff: AsyncClient, world: World
    ) -> None:
        await as_staff.post("/api/door/register/arrivals", json={"child_id": str(world.child.id)})
        results = (
            await as_staff.post(
                "/api/door/register/sync",
                json={
                    "marks": [
                        {
                            "child_id": str(world.child.id),
                            "occurred_at": datetime.now(UTC).isoformat(),
                            "client_id": "phone-late-001",
                        }
                    ]
                },
            )
        ).json()["results"]
        assert results[0]["status"] == "already"


class TestAbsences:
    async def test_a_parent_says_their_child_is_off_and_the_register_shows_it(
        self, as_parent: AsyncClient, as_staff: AsyncClient, world: World
    ) -> None:
        given = await as_parent.post(
            f"/api/parent/children/{world.child.id}/absences",
            json={"day": today(), "reason": "ill", "note": "Temperature"},
        )
        assert given.status_code == 201, given.text
        rows = {
            r["full_name"]: r for r in (await as_staff.get("/api/door/register")).json()["children"]
        }
        assert rows["Maya Parent"]["absence_reason"] == "ill"
        listed = (await as_parent.get(f"/api/parent/children/{world.child.id}/absences")).json()
        assert len(listed) == 1
        cancelled = await as_parent.post(f"/api/parent/absences/{given.json()['id']}/cancel")
        assert cancelled.status_code == 200
        assert (await as_parent.get(f"/api/parent/children/{world.child.id}/absences")).json() == []

    async def test_an_absence_cannot_be_given_for_the_past_or_for_another_family(
        self, as_parent: AsyncClient, world: World
    ) -> None:
        yesterday = (datetime.now(LONDON).date() - timedelta(days=1)).isoformat()
        past = await as_parent.post(
            f"/api/parent/children/{world.child.id}/absences",
            json={"day": yesterday, "reason": "ill"},
        )
        assert past.status_code == 400
        theirs = await as_parent.post(
            f"/api/parent/children/{world.unrelated_child.id}/absences",
            json={"day": today(), "reason": "ill"},
        )
        assert theirs.status_code == 404

    async def test_staff_record_an_absence_phoned_in(
        self, as_staff: AsyncClient, world: World
    ) -> None:
        given = await as_staff.post(
            "/api/door/register/absences",
            json={
                "child_id": str(world.unrelated_child.id),
                "day": today(),
                "reason": "appointment",
            },
        )
        assert given.status_code == 201, given.text

    async def test_a_child_already_in_cannot_be_marked_absent_today(
        self, as_parent: AsyncClient, as_staff: AsyncClient, world: World
    ) -> None:
        await as_staff.post("/api/door/register/arrivals", json={"child_id": str(world.child.id)})
        late = await as_parent.post(
            f"/api/parent/children/{world.child.id}/absences",
            json={"day": today(), "reason": "ill"},
        )
        assert late.status_code == 400


def at(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(datetime.now(LONDON).date(), time(hour, minute), tzinfo=LONDON)


class TestWhenTheCheckIsDue:
    def test_only_inside_the_hours_after_the_chosen_time(self) -> None:
        nursery = Nursery(name="N", slug="n", timezone="Europe/London", active=True)
        assert alerts.due(nursery, at(10)) is None
        nursery.arrival_alert_at = time(9, 30)
        assert alerts.due(nursery, at(9, 29)) is None
        assert alerts.due(nursery, at(9, 30)) == at(9, 30).date()
        assert alerts.due(nursery, at(13, 29)) == at(9, 30).date()
        assert alerts.due(nursery, at(13, 31)) is None
        nursery.active = False
        assert alerts.due(nursery, at(10)) is None


class TestNonArrivalAlerts:
    async def _run(self, world: World) -> object:
        async with db.sessionmaker()() as s:
            nursery = await s.get(Nursery, world.nursery.id)
            assert nursery is not None
            nursery.arrival_alert_at = time(9, 30)
            run = await alerts.run_for(s, nursery, datetime.now(LONDON).date(), datetime.now(UTC))
            await s.commit()
            return run

    async def test_both_parents_of_a_missing_child_are_told_once(
        self, as_staff: AsyncClient, world: World
    ) -> None:
        await every_day(world.child, world.sibling, world.unrelated_child)
        # The register was taken: two of three are in.
        for c in (world.sibling, world.unrelated_child):
            await as_staff.post("/api/door/register/arrivals", json={"child_id": str(c.id)})
        OUTBOX.messages.clear()
        run = await self._run(world)
        assert run is not None and run.alerted == 1 and run.suppressed_reason is None
        told = sorted(m["To"] for m in OUTBOX.messages)
        assert told == ["dad@acorns.example.com", "parent@acorns.example.com"]
        assert "Maya Parent has not been marked in" in OUTBOX.messages[0]["Subject"]
        # A second run the same day sends nothing more.
        OUTBOX.messages.clear()
        assert await self._run(world) is None
        assert OUTBOX.messages == []

    async def test_absent_collected_and_unbooked_children_are_not_alerted(
        self, as_parent: AsyncClient, as_staff: AsyncClient, world: World
    ) -> None:
        await every_day(world.child, world.unrelated_child)
        async with db.sessionmaker()() as s:
            sibling = await s.get(Child, world.sibling.id)
            assert sibling is not None
            weekday = str(datetime.now(LONDON).isoweekday())
            sibling.session_days = "".join(d for d in "1234567" if d != weekday)
            await s.commit()
        await as_parent.post(
            f"/api/parent/children/{world.child.id}/absences",
            json={"day": today(), "reason": "ill"},
        )
        await as_staff.post(
            "/api/door/register/arrivals", json={"child_id": str(world.unrelated_child.id)}
        )
        OUTBOX.messages.clear()
        run = await self._run(world)
        assert run is not None and run.alerted == 0 and run.expected == 1
        assert OUTBOX.messages == []

    async def test_no_parent_is_emailed_when_nobody_was_marked_in(self, world: World) -> None:
        await every_day(world.child, world.sibling, world.unrelated_child)
        OUTBOX.messages.clear()
        run = await self._run(world)
        assert run is not None and run.alerted == 0
        assert run.suppressed_reason and "register may not have been taken" in run.suppressed_reason
        assert [m["To"] for m in OUTBOX.messages] == ["admin@acorns.example.com"]

    async def test_no_parent_is_emailed_when_most_of_the_room_is_missing(
        self, as_staff: AsyncClient, session: AsyncSession, world: World
    ) -> None:
        extra = [
            Child(nursery_id=world.nursery.id, full_name=f"Extra Child{n}", session_days="1234567")
            for n in range(5)
        ]
        session.add_all(extra)
        await session.commit()
        await every_day(world.child, world.sibling, world.unrelated_child)
        await as_staff.post("/api/door/register/arrivals", json={"child_id": str(world.child.id)})
        OUTBOX.messages.clear()
        run = await self._run(world)
        assert run is not None and run.alerted == 0 and run.missing == 7
        assert run.suppressed_reason and "7 of 8" in run.suppressed_reason
        assert all(m["To"] == "admin@acorns.example.com" for m in OUTBOX.messages)


class TestManagerSettings:
    async def test_the_alert_time_and_booked_days_are_set_by_the_manager(
        self, as_admin: AsyncClient, as_staff: AsyncClient, world: World
    ) -> None:
        set_time = await as_admin.put("/api/admin/alerts", json={"arrival_alert_at": "09:45"})
        assert set_time.json()["arrival_alert_at"] == "09:45:00"
        assert (
            await as_staff.put("/api/admin/alerts", json={"arrival_alert_at": "10:00"})
        ).status_code == 403
        days = await as_admin.patch(
            f"/api/admin/children/{world.child.id}", json={"session_days": "135"}
        )
        assert days.json()["session_days"] == "135"
        bad = await as_admin.patch(
            f"/api/admin/children/{world.child.id}", json={"session_days": "19"}
        )
        assert bad.status_code == 400
        off = await as_admin.put("/api/admin/alerts", json={"arrival_alert_at": None})
        assert off.json()["arrival_alert_at"] is None

    async def test_today_shows_the_register(
        self, as_admin: AsyncClient, as_staff: AsyncClient, world: World
    ) -> None:
        await every_day(world.child, world.sibling, world.unrelated_child)
        await as_staff.post("/api/door/register/arrivals", json={"child_id": str(world.child.id)})
        summary = (await as_admin.get("/api/admin/today")).json()
        assert summary["expected"] == 3 and summary["arrived"] == 1
        assert sorted(summary["not_arrived"]) == ["Leo Parent", "Zara Other"]


class TestAChildWithNoParentLinked:
    async def test_the_managers_are_told_instead(self, as_staff: AsyncClient, world: World) -> None:
        await every_day(world.child, world.sibling, world.unrelated_child)
        for c in (world.child, world.sibling):
            await as_staff.post("/api/door/register/arrivals", json={"child_id": str(c.id)})
        OUTBOX.messages.clear()
        async with db.sessionmaker()() as s:
            nursery = await s.get(Nursery, world.nursery.id)
            assert nursery is not None
            nursery.arrival_alert_at = time(9, 30)
            run = await alerts.run_for(s, nursery, datetime.now(LONDON).date(), datetime.now(UTC))
            await s.commit()
        assert run is not None and run.missing == 1 and run.alerted == 0
        assert [m["To"] for m in OUTBOX.messages] == ["admin@acorns.example.com"]
        assert "Zara Other" in OUTBOX.messages[0].get_content()
