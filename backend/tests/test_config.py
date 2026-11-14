"""Settings read from a hosted environment."""

from __future__ import annotations

from app.config import Settings


def test_a_hosts_postgres_url_is_used_with_asyncpg() -> None:
    settings = Settings(DATABASE_URL="postgres://u:p@dpg-abc-a:5432/collector", _env_file=None)  # type: ignore[call-arg]
    assert settings.DATABASE_URL == "postgresql+asyncpg://u:p@dpg-abc-a:5432/collector"


def test_an_explicit_driver_is_left_alone() -> None:
    url = "sqlite+aiosqlite:///./collector.db"
    assert url == Settings(DATABASE_URL=url, _env_file=None).DATABASE_URL  # type: ignore[call-arg]
