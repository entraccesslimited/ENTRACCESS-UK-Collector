"""Remove test accounts, and the test nurseries they made.

For tidying up after testing on the live site. Everything is found by the
email domain the test accounts used, and only a reserved domain is accepted
(example.com and its subdomains, .test, .example, .invalid), so a real
nursery's people can never match.

    python -m app.maintenance.purge_test_accounts --domain collector-e2e.example.com
    python -m app.maintenance.purge_test_accounts --domain collector-e2e.example.com --yes

Without --yes it only lists what it would remove. With it, it removes every
nursery whose people are all at the domain (with its children, collectors,
door checks, handovers and activity), then any other account, operator or
website enquiry at the domain.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from sqlalchemy import delete, func, select

from app.db import sessionmaker
from app.models import (
    AuditEvent,
    Authorisation,
    Child,
    DoorCheck,
    Enquiry,
    Handover,
    Nursery,
    Operator,
    ParentLink,
    Restriction,
    SignOut,
    SignOutImport,
    User,
)
from app.notify import reserved_address

# Children of a nursery, in an order that respects every foreign key.
NURSERY_TABLES: tuple[Any, ...] = (
    Handover,
    SignOut,
    DoorCheck,
    Restriction,
    SignOutImport,
    ParentLink,
    Authorisation,
    AuditEvent,
    User,
    Child,
)
# A purge that matches more than this is not a tidy-up after a test run.
LIMIT = 20


async def purge(domain: str, *, apply: bool) -> int:
    suffix = f"@{domain}"
    async with sessionmaker()() as session:
        users = (
            await session.scalars(select(User).where(func.lower(User.email).endswith(suffix)))
        ).all()
        operators = (
            await session.scalars(
                select(Operator).where(func.lower(Operator.email).endswith(suffix))
            )
        ).all()
        enquiries = (
            await session.scalars(select(Enquiry).where(func.lower(Enquiry.email).endswith(suffix)))
        ).all()
        found = len(users) + len(operators)
        if found > LIMIT:
            print(f"✗ {found} accounts at {domain}; refusing more than {LIMIT}.")
            return 1

        nurseries: list[Nursery] = []
        for nursery_id in sorted({u.nursery_id for u in users}, key=str):
            others = await session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.nursery_id == nursery_id, ~func.lower(User.email).endswith(suffix))
            )
            nursery = await session.get(Nursery, nursery_id)
            if nursery is None:
                continue
            if others:
                print(f"  keep nursery {nursery.slug}: it has {others} account(s) elsewhere")
                continue
            nurseries.append(nursery)

        for nursery in nurseries:
            print(f"  nursery  {nursery.slug} ({nursery.name})")
        for user in users:
            print(f"  account  {user.email} ({user.role.value})")
        for operator in operators:
            print(f"  operator {operator.email}")
        for enquiry in enquiries:
            print(f"  enquiry  {enquiry.email} ({enquiry.nursery_name})")

        if not apply:
            print("Nothing removed. Run again with --yes to remove the above.")
            return 0

        ids = [n.id for n in nurseries]
        for table in NURSERY_TABLES:
            await session.execute(delete(table).where(table.nursery_id.in_(ids)))
        await session.execute(delete(Nursery).where(Nursery.id.in_(ids)))
        await session.execute(delete(User).where(func.lower(User.email).endswith(suffix)))
        await session.execute(delete(Operator).where(func.lower(Operator.email).endswith(suffix)))
        await session.execute(delete(Enquiry).where(func.lower(Enquiry.email).endswith(suffix)))
        await session.commit()
        left = sum(
            [
                await session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(func.lower(model.email).endswith(suffix))
                )
                or 0
                for model in (User, Operator, Enquiry)
            ]
        )
        print(
            f"PURGED {domain}: {len(nurseries)} nursery(ies), {len(users)} account(s), "
            f"{len(operators)} operator(s), {len(enquiries)} enquiry(ies); {left} left"
        )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True, help="Email domain of the test accounts.")
    parser.add_argument("--yes", action="store_true", help="Remove, rather than list.")
    args = parser.parse_args()
    domain = args.domain.strip().lower().lstrip("@")
    if not reserved_address(f"x@{domain}"):
        raise SystemExit(f"✗ {domain} is not a reserved test domain; real accounts could match it.")
    raise SystemExit(asyncio.run(purge(domain, apply=args.yes)))


if __name__ == "__main__":
    main()
