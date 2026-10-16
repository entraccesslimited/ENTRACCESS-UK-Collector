"""Create a company-portal operator account, from a shell.

Deliberately not possible over the API: an endpoint that could make an
operator would be worth attacking, and having a shell on the server is the
same bar as having the database.

    python -m app.create_operator --email you@entraccess.co.uk --name "Your Name"

The password is prompted for, so it never reaches an argument list, an
environment variable or the shell history.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass

from sqlalchemy import func, select

from app.db import sessionmaker
from app.models import Operator, User
from app.security import hash_password, password_problem


async def create(email: str, name: str, password: str) -> None:
    async with sessionmaker()() as session:
        for model in (Operator, User):
            if await session.scalar(select(model).where(func.lower(model.email) == email.lower())):
                raise SystemExit("Someone already uses that email address.")
        session.add(
            Operator(email=email.lower(), full_name=name, password_hash=hash_password(password))
        )
        await session.commit()
    print(f"Operator {email} created. Sign in at /company.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Password (at least 10 characters): ")
    problem = password_problem(password)
    if problem:
        raise SystemExit(problem)
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("The passwords do not match.")
    asyncio.run(create(args.email, args.name, password))


if __name__ == "__main__":
    main()
