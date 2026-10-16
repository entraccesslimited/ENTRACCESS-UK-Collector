"""Settings, read from the environment.

Two secrets matter and neither has a usable default outside development:
`SECRET_KEY` signs sessions, and `PASS_SIGNING_KEY` signs collectors' passes and
derives their daily codes. Changing the second invalidates every pass in
circulation, which is the right outcome after a leak and a surprising one at
any other time.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-secret-key-change-me-dev-secret-key"
DEV_PASS_KEY = "dev-pass-signing-key-change-me-dev-pass"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    APP_NAME: str = "ENTRACCESS UK Collector"
    APP_BASE_URL: str = "http://localhost:8090"

    DATABASE_URL: str = "sqlite+aiosqlite:///./collector.db"

    SECRET_KEY: str = DEV_SECRET
    PASS_SIGNING_KEY: str = DEV_PASS_KEY
    SESSION_HOURS: int = 12
    # A parent's own phone, opened like an app: signing in twice a day would
    # be the reason they stopped using it. Staff and company sessions keep the
    # short one, because those devices are shared.
    PARENT_SESSION_DAYS: int = 30

    # The nursery's local time decides what "today" means for a daily code and
    # for a one-off collection on a given date.
    DEFAULT_TIMEZONE: str = "Europe/London"

    # How many wrong codes for one child, in the window, before code entry for
    # that child is paused. A pass scan is unaffected: it cannot be guessed.
    CODE_ATTEMPT_LIMIT: int = 5
    CODE_ATTEMPT_WINDOW_MINUTES: int = 15

    EMAIL_ENABLED: bool = False
    EMAIL_FROM: str = "ENTRACCESS UK <no-reply@localhost>"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_STARTTLS: bool = False
    # Where enquiries from the website are emailed. Unset: they are only kept
    # for the company portal.
    SUPPORT_EMAIL: str | None = None

    @model_validator(mode="after")
    def _no_dev_secrets_in_production(self) -> Settings:
        if self.ENVIRONMENT in {"staging", "production"}:
            if self.SECRET_KEY == DEV_SECRET or len(self.SECRET_KEY) < 32:
                raise ValueError("Set a SECRET_KEY of at least 32 characters outside development.")
            if self.PASS_SIGNING_KEY == DEV_PASS_KEY or len(self.PASS_SIGNING_KEY) < 32:
                raise ValueError(
                    "Set a PASS_SIGNING_KEY of at least 32 characters outside development."
                )
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.ENVIRONMENT in {"staging", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
