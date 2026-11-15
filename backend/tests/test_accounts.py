"""The emails an account gets, and the links in them.

Somebody added to a nursery is told by email. Without a password they are
invited to choose their own; with one, they are told where to sign in and
never what the password is. A link to choose a password works once.
"""

from __future__ import annotations

from email.message import EmailMessage

from httpx import ASGITransport, AsyncClient

from app.notify import OUTBOX
from tests.conftest import PASSWORD, World

NEW_PARENT = {"email": "jo@example.com", "full_name": "Jo Rivers", "role": "parent"}
CHOSEN = "a-password-of-my-own"


def _to(address: str) -> list[EmailMessage]:
    return [m for m in OUTBOX.messages if m["To"] == address]


def _body(message: EmailMessage) -> str:
    return message.get_content()


def _token(message: EmailMessage) -> str:
    link = next(line for line in _body(message).splitlines() if "/set-password?token=" in line)
    return link.split("token=")[1].strip()


async def _client(app: object) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
        headers={"X-Requested-With": "fetch"},
    )


class TestInvitations:
    async def test_no_password_sends_an_invitation(self, as_admin: AsyncClient) -> None:
        added = await as_admin.post("/api/admin/people", json=NEW_PARENT)
        assert added.status_code == 201, added.text
        assert added.json()["invitation_pending"] is True

        [message] = _to(NEW_PARENT["email"])
        assert "set up your ENTRACCESS UK Collector account" in message["Subject"]
        body = _body(message)
        assert "a parent account" in body
        assert "/set-password?token=" in body

    async def test_the_account_cannot_be_used_until_the_link_is_followed(
        self, app: object, as_admin: AsyncClient
    ) -> None:
        await as_admin.post("/api/admin/people", json=NEW_PARENT)
        async with await _client(app) as client:
            refused = await client.post(
                "/api/auth/sign-in", json={"email": NEW_PARENT["email"], "password": "!invited"}
            )
            assert refused.status_code == 401

            token = _token(_to(NEW_PARENT["email"])[0])
            info = await client.get("/api/auth/set-password", params={"token": token})
            assert info.status_code == 200
            assert info.json() == {
                "full_name": "Jo Rivers",
                "email": NEW_PARENT["email"],
                "first_time": True,
            }

            chosen = await client.post(
                "/api/auth/set-password", json={"token": token, "password": CHOSEN}
            )
            assert chosen.status_code == 200, chosen.text
            # Signed in by choosing it.
            assert (await client.get("/api/auth/me")).json()["role"] == "parent"

            again = await client.post(
                "/api/auth/set-password", json={"token": token, "password": "another-one-entirely"}
            )
            assert again.status_code == 400

            signin = await client.post(
                "/api/auth/sign-in", json={"email": NEW_PARENT["email"], "password": CHOSEN}
            )
            assert signin.status_code == 200

    async def test_a_resend_sends_a_fresh_link(self, as_admin: AsyncClient) -> None:
        added = await as_admin.post("/api/admin/people", json=NEW_PARENT)
        resent = await as_admin.post(f"/api/admin/people/{added.json()['id']}/resend-invitation")
        assert resent.status_code == 200, resent.text
        assert len(_to(NEW_PARENT["email"])) == 2

    async def test_no_resend_for_somebody_with_a_password(
        self, world: World, as_admin: AsyncClient
    ) -> None:
        """A set-password link for a working account would be a way to take it over."""
        refused = await as_admin.post(f"/api/admin/people/{world.parent.id}/resend-invitation")
        assert refused.status_code == 400
        assert _to(world.parent.email) == []


class TestAStartingPassword:
    async def test_they_are_told_where_to_sign_in_never_the_password(
        self, as_admin: AsyncClient
    ) -> None:
        starting = "Starting-Pass-2026"
        added = await as_admin.post(
            "/api/admin/people", json={**NEW_PARENT, "role": "staff", "password": starting}
        )
        assert added.status_code == 201, added.text
        assert added.json()["invitation_pending"] is False

        [message] = _to(NEW_PARENT["email"])
        assert "account is ready" in message["Subject"]
        body = _body(message)
        assert "a room leader account" in body
        assert "/sign-in" in body
        assert starting not in body
        assert "set-password" not in body

    async def test_a_new_nursery_manager_is_invited(self, as_operator: AsyncClient) -> None:
        created = await as_operator.post(
            "/api/company/nurseries",
            json={
                "name": "Rosebud Nursery (demo)",
                "slug": "rosebud",
                "manager_name": "Rosa Manager",
                "manager_email": "rosa@rosebud.example.com",
            },
        )
        assert created.status_code == 201, created.text
        [message] = _to("rosa@rosebud.example.com")
        assert "a manager account" in _body(message)
        assert "/set-password?token=" in _body(message)


class TestForgottenPasswords:
    async def test_a_reset_link_works_once(self, app: object, world: World) -> None:
        async with await _client(app) as client:
            asked = await client.post(
                "/api/auth/forgot-password", json={"email": world.parent.email}
            )
            assert asked.status_code == 202
            [message] = _to(world.parent.email)
            token = _token(message)
            assert (await client.get("/api/auth/set-password", params={"token": token})).json()[
                "first_time"
            ] is False

            # The old password still works until the link is used.
            old = await client.post(
                "/api/auth/sign-in", json={"email": world.parent.email, "password": PASSWORD}
            )
            assert old.status_code == 200

            chosen = await client.post(
                "/api/auth/set-password", json={"token": token, "password": CHOSEN}
            )
            assert chosen.status_code == 200, chosen.text
            stale = await client.post(
                "/api/auth/set-password", json={"token": token, "password": "yet-another-password"}
            )
            assert stale.status_code == 400

    async def test_the_answer_does_not_reveal_who_has_an_account(
        self, anonymous: AsyncClient
    ) -> None:
        known = await anonymous.post(
            "/api/auth/forgot-password", json={"email": "nobody@example.com"}
        )
        assert known.status_code == 202
        assert OUTBOX.messages == []

    async def test_requests_are_limited(self, world: World, anonymous: AsyncClient) -> None:
        """Three an hour, so the form cannot be used to flood somebody's inbox."""
        for _ in range(5):
            await anonymous.post("/api/auth/forgot-password", json={"email": world.parent.email})
        assert len(_to(world.parent.email)) == 3

    async def test_a_forged_link_is_refused(self, anonymous: AsyncClient) -> None:
        forged = await anonymous.post(
            "/api/auth/set-password", json={"token": "not-a-real-token-at-all", "password": CHOSEN}
        )
        assert forged.status_code == 400


ENQUIRY = {
    "contact_name": "Bea Bluebell",
    "nursery_name": "Bluebell Day Nursery",
    "email": "bea@bluebell.example.com",
    "message": "Visit http://phish.example/claim for a prize",
}


class TestEnquiryAcknowledgement:
    async def test_the_nursery_is_told_we_have_it(self, anonymous: AsyncClient) -> None:
        sent = await anonymous.post("/api/public/enquiries", json=ENQUIRY)
        assert sent.status_code == 201, sent.text
        [ack] = _to(ENQUIRY["email"])
        assert ack["Subject"] == "We have your enquiry — ENTRACCESS UK Collector"
        body = _body(ack)
        assert "Bluebell Day Nursery" in body
        assert "within two working days" in body
        # Their words are not quoted back to whatever address was typed in.
        assert "phish.example" not in body
