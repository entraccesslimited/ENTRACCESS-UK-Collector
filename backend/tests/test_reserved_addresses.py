"""Mail is never sent to an address at a domain that cannot receive it.

Test accounts live at reserved names such as `.test` and `example.com`. A
message to one can only bounce, and a relay that sees enough bounces stops
sending the real mail too.
"""

from __future__ import annotations

from typing import Any

import pytest

from app import notify
from app.config import get_settings


@pytest.mark.parametrize(
    ("address", "reserved"),
    [
        ("parent@example.com", True),
        ("parent@nursery.example.org", True),
        ("x@anything.test", True),
        ("x@nowhere.invalid", True),
        ("x@school.example", True),
        ("x@localhost", True),
        ("support@entraccess-collector.co.uk", False),
        ("someone@example.co.uk", False),
        ("someone@gmail.com", False),
    ],
)
def test_reserved_names(address: str, reserved: bool) -> None:
    assert notify.reserved_address(address) is reserved


async def test_a_reserved_address_is_never_handed_to_the_relay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[Any] = []

    async def fake_send(message: Any, **_: Any) -> None:
        sent.append(message)

    monkeypatch.setattr(notify.aiosmtplib, "send", fake_send)
    monkeypatch.setattr(get_settings(), "EMAIL_ENABLED", True)

    await notify.send("parent@family.test", "Hello", "Body")
    assert sent == []

    await notify.send("support@entraccess-collector.co.uk", "Hello", "Body")
    assert [m["To"] for m in sent] == ["support@entraccess-collector.co.uk"]
