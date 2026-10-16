"""Demo data for local development: one nursery, its people and children.

Everything here is made up. It refuses to run in production, and it does
nothing if the demo nursery already exists.

    python -m app.seed
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.config import get_settings
from app.db import sessionmaker
from app.models import Child, Nursery, Operator, ParentLink, Role, User
from app.security import hash_password

DEMO_PASSWORD = "demo-password-123"
OPERATOR_EMAIL = "operator@demo.example.com"

PEOPLE = [
    ("admin@demo.example.com", "Amira Khan", Role.ADMIN),
    ("staff@demo.example.com", "Sam Taylor", Role.STAFF),
    ("parent@demo.example.com", "Priya Shah", Role.PARENT),
    ("dad@demo.example.com", "Dev Shah", Role.PARENT),
]
CHILDREN = [("Maya Shah", "Butterflies"), ("Leo Shah", "Caterpillars"), ("Zara Ali", "Butterflies")]


async def seed() -> None:
    if get_settings().ENVIRONMENT == "production":
        raise SystemExit("Refusing to load demo data into production.")
    async with sessionmaker()() as session:
        if not await session.scalar(select(Operator).where(Operator.email == OPERATOR_EMAIL)):
            session.add(
                Operator(
                    email=OPERATOR_EMAIL,
                    full_name="ENTRACCESS UK (demo operator)",
                    password_hash=hash_password(DEMO_PASSWORD),
                )
            )
            await session.commit()
            print(f"Company portal: {OPERATOR_EMAIL}, password {DEMO_PASSWORD}")
        if await session.scalar(select(Nursery).where(Nursery.slug == "demo")):
            print("Demo nursery already exists. Nothing more to do.")
            return
        nursery = Nursery(
            name="Little Acorns Nursery (demo)", slug="demo", timezone="Europe/London"
        )
        session.add(nursery)
        await session.flush()
        users = {
            email: User(
                nursery_id=nursery.id,
                email=email,
                full_name=name,
                role=role,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            for email, name, role in PEOPLE
        }
        children = [Child(nursery_id=nursery.id, full_name=n, room=r) for n, r in CHILDREN]
        session.add_all([*users.values(), *children])
        await session.flush()
        for parent in ("parent@demo.example.com", "dad@demo.example.com"):
            for child in children[:2]:
                session.add(
                    ParentLink(nursery_id=nursery.id, parent_id=users[parent].id, child_id=child.id)
                )
        await session.commit()
    print("Demo nursery loaded. Sign in with any of these, password", DEMO_PASSWORD)
    labels = {Role.ADMIN: "manager", Role.STAFF: "room leader", Role.PARENT: "parent"}
    for email, _name, role in PEOPLE:
        print(f"  {labels[role]:12} {email}")


if __name__ == "__main__":
    asyncio.run(seed())
