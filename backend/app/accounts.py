"""The emails an account gets: an invitation, a welcome, a reset link.

Somebody added to a nursery hears about it from us, not only from whoever
added them. Left without a password, they are sent a link to choose their
own, so nobody else ever knows it. Given one by their manager, they are told
where to sign in and never what the password is: that is handed over in
person, and an email is the one place it must not travel.
"""

from __future__ import annotations

from urllib.parse import quote

from app.config import get_settings
from app.models import Nursery, Role, User
from app.notify import send
from app.security import INVITE_LINK, RESET_LINK, issue_password_link

# The same words the People page uses, so the email and the screen agree.
ROLE_LABELS: dict[Role, str] = {
    Role.ADMIN: "manager",
    Role.STAFF: "room leader",
    Role.PARENT: "parent",
}

# What each kind of account is for, in a sentence, so the email says why it
# matters rather than only that it exists.
_WHAT_IT_DOES: dict[Role, str] = {
    Role.ADMIN: "You can add the nursery's children, parents and staff, and see every handover.",
    Role.STAFF: "You check collectors at the door and record who each child left with.",
    Role.PARENT: (
        "You choose who may collect your child, send them a pass, and are told "
        "each time your child is collected."
    ),
}


def _base() -> str:
    return get_settings().APP_BASE_URL.rstrip("/")


def set_password_url(token: str) -> str:
    return f"{_base()}/set-password?token={quote(token)}"


def _article(label: str) -> str:
    return "an" if label[0] in "aeiou" else "a"


async def send_invitation(user: User, nursery: Nursery) -> None:
    """A link to choose a first password. The account works once it is used."""
    label = ROLE_LABELS[user.role]
    link = set_password_url(issue_password_link(user.id, user.password_hash, INVITE_LINK))
    await send(
        user.email,
        f"{nursery.name}: set up your ENTRACCESS UK Collector account",
        "\n".join(
            [
                f"Hello {user.full_name},",
                "",
                f"{nursery.name} has made you {_article(label)} {label} account on "
                "ENTRACCESS UK Collector, which keeps a record of who collects each child.",
                _WHAT_IT_DOES[user.role],
                "",
                "Choose your password here:",
                link,
                "",
                "The link works once and lasts seven days. Nobody else knows the "
                "password you choose, including the nursery.",
                "",
                f"If you were not expecting this, ignore it and tell {nursery.name}. "
                "The account cannot be used until somebody follows the link.",
            ]
        ),
        reply_to=get_settings().SUPPORT_EMAIL,
    )


async def send_welcome(user: User, nursery: Nursery) -> None:
    """Where to sign in, for somebody whose manager set their first password."""
    label = ROLE_LABELS[user.role]
    await send(
        user.email,
        f"{nursery.name}: your ENTRACCESS UK Collector account is ready",
        "\n".join(
            [
                f"Hello {user.full_name},",
                "",
                f"{nursery.name} has made you {_article(label)} {label} account on "
                "ENTRACCESS UK Collector, which keeps a record of who collects each child.",
                _WHAT_IT_DOES[user.role],
                "",
                "Sign in here:",
                f"{_base()}/sign-in",
                "",
                f"{nursery.name} set a first password for you and will give it to you "
                "in person. This email never contains it. You can choose a new one at "
                'any time with "Forgot your password?" on the sign-in page.',
                "",
                f"If you were not expecting this, tell {nursery.name}.",
            ]
        ),
        reply_to=get_settings().SUPPORT_EMAIL,
    )


async def send_reset(user: User) -> None:
    """A link to choose a new password, for somebody who has lost theirs."""
    link = set_password_url(issue_password_link(user.id, user.password_hash, RESET_LINK))
    await send(
        user.email,
        "Choose a new ENTRACCESS UK Collector password",
        "\n".join(
            [
                f"Hello {user.full_name},",
                "",
                "Somebody asked to reset the password for this account. Choose a new one here:",
                link,
                "",
                "The link works once and lasts an hour. Your current password keeps "
                "working until you use it.",
                "",
                "If this was not you, ignore this email. Nothing has changed.",
            ]
        ),
        reply_to=get_settings().SUPPORT_EMAIL,
    )
