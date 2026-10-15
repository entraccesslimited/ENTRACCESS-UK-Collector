"""The migrations build the same schema the models describe."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.db import Base

ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_creates_every_table(tmp_path: Path) -> None:
    db = tmp_path / "migrated.db"
    env = {"DATABASE_URL": f"sqlite+aiosqlite:///{db}", "PATH": "/usr/bin:/bin"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True
    )
    tables = set(inspect(create_engine(f"sqlite:///{db}")).get_table_names())
    assert set(Base.metadata.tables) <= tables
