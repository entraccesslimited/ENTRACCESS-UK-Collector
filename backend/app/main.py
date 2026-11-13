"""The application."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.collection import CollectionError
from app.config import get_settings
from app.routers import admin, auth, company, door, parent, public, reconciliation


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
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
        company.router,
        public.router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
