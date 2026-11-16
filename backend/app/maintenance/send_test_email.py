"""Send one test email through the deployment's own mail settings.

    python -m app.maintenance.send_test_email --to support@entraccess.co.uk

Prints SENT on success. On failure it prints the reason and exits 1, so a
Render job shows as failed rather than succeeded.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings
from app.notify import reserved_address


def compose(to: str) -> EmailMessage:
    settings = get_settings()
    now = datetime.now(UTC).strftime("%H:%M UTC on %d %b %Y")
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = "Test email from ENTRACCESS UK Collector"
    message.set_content(
        f"This is a test email sent by ENTRACCESS UK Collector ({settings.APP_BASE_URL}) "
        f"through {settings.SMTP_HOST} at {now}.\n\nNo action is needed."
    )
    return message


async def send(message: EmailMessage) -> str:
    settings = get_settings()
    if not settings.EMAIL_ENABLED:
        raise RuntimeError("EMAIL_ENABLED is off, so this deployment sends no mail.")
    response = await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        start_tls=settings.SMTP_STARTTLS,
        timeout=20,
    )
    return str(response[1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", required=True, help="Address to send the test to.")
    args = parser.parse_args()
    to = args.to.strip()
    if reserved_address(to):
        raise SystemExit(f"FAILED: {to} is at a reserved domain and cannot receive mail.")
    message = compose(to)
    try:
        reply = asyncio.run(send(message))
    except Exception as exc:  # every failure is reported the same way
        print(f"FAILED: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
    print(f"SENT to {to} from {message['From']}: {reply}")


if __name__ == "__main__":
    main()
