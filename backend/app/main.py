"""The application."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import alerts, photos
from app.collection import CollectionError
from app.config import get_settings
from app.db import sessionmaker
from app.routers import (
    admin,
    auth,
    company,
    contacts,
    door,
    parent,
    public,
    reconciliation,
    reports,
)

log = logging.getLogger("collector.housekeeping")


async def housekeeping_once() -> None:
    async with sessionmaker()() as session:
        await alerts.run_due(session)
        await photos.purge_unneeded(session, datetime.now(UTC))
        await session.commit()


async def _housekeeping_loop(every: int) -> None:
    while True:
        try:
            await housekeeping_once()
        except Exception:
            log.exception("housekeeping failed")
        await asyncio.sleep(every)


def create_app() -> FastAPI:
    settings = get_settings()

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        task = None
        if settings.HOUSEKEEPING_ENABLED and settings.ENVIRONMENT != "test":
            task = asyncio.create_task(_housekeeping_loop(settings.HOUSEKEEPING_SECONDS))
        yield
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
    )

    @app.exception_handler(CollectionError)
    async def _refused(_request: Request, exc: CollectionError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    @app.middleware("http")
    async def _headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    for router in (
        auth.router,
        parent.router,
        door.router,
        admin.router,
        reconciliation.router,
        contacts.router,
        reports.router,
        company.router,
        public.router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
