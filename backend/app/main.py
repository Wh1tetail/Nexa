import asyncio
import contextlib
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.exceptions import AppError
from app.core.i18n import lang_from_header, request_lang, tr, validation_message
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.services.email_outbox import process_email_outbox
from app.services.storage_cleanup import sweep_orphans
from app.services.realtime import broker, listener
from app.services.subscription_service import check_expirations

# Windows consoles default to a legacy code page: force UTF-8 so Cyrillic logs stay readable.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, ValueError):
        _stream.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


async def _subscription_watcher() -> None:
    """Periodically notify about expiring / expired subscriptions."""
    while True:
        try:
            with SessionLocal() as db:
                await asyncio.to_thread(check_expirations, db)
        except Exception:  # pragma: no cover - keep the loop alive
            log.exception("Subscription check failed")
        await asyncio.sleep(settings.SUBSCRIPTION_CHECK_INTERVAL_MINUTES * 60)


async def _email_outbox_worker() -> None:
    """E-mail copies of notifications / chat messages still unread after a delay."""
    while True:
        try:
            with SessionLocal() as db:
                await asyncio.to_thread(process_email_outbox, db)
        except Exception:  # pragma: no cover - keep the loop alive
            log.exception("E-mail outbox failed")
        await asyncio.sleep(settings.EMAIL_OUTBOX_INTERVAL_SECONDS)


async def _storage_sweeper() -> None:
    """Deletes stored files whose rows were removed by database cascades."""
    while True:
        await asyncio.sleep(settings.STORAGE_SWEEP_INTERVAL_HOURS * 3600)
        try:
            with SessionLocal() as db:
                await asyncio.to_thread(sweep_orphans, db)
        except Exception:  # pragma: no cover - keep the loop alive
            log.exception("Storage sweep failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    broker.bind_loop(asyncio.get_running_loop())
    if settings.REALTIME_ENABLED:
        listener.start()
    tasks = []
    if settings.ENVIRONMENT != "test":
        tasks = [asyncio.create_task(_subscription_watcher()), asyncio.create_task(_email_outbox_worker())]
        if settings.STORAGE_SWEEP_INTERVAL_HOURS > 0:
            tasks.append(asyncio.create_task(_storage_sweeper()))
    yield
    if settings.REALTIME_ENABLED:
        await asyncio.to_thread(listener.stop)
    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LanguageMiddleware:
    """Pure ASGI middleware: the request's language (Accept-Language) for texts
    built while handling it. Context variables reach sync endpoints too."""

    def __init__(self, app_) -> None:
        self.app = app_

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        header = dict(scope.get("headers") or []).get(b"accept-language", b"").decode("latin-1")
        token = request_lang.set(lang_from_header(header))
        try:
            await self.app(scope, receive, send)
        finally:
            request_lang.reset(token)


app.add_middleware(LanguageMiddleware)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Errors in the request's language: our AppError carries its template and
    values; other texts (e.g. the login limiter) are looked up as they are."""
    content: dict = {}
    if isinstance(exc, AppError):
        content["detail"] = tr(exc.template, **exc.params)
        if exc.code:
            content["code"] = exc.code
    elif isinstance(exc.detail, str):
        content["detail"] = tr(exc.detail)
    else:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return a readable first error message (in the request's language) plus the full list."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    msg = validation_message(first, request_lang.get()) if first else tr("Некорректные данные")
    parts = list(first.get("loc", []))
    if parts and parts[0] in ("body", "query", "path", "form"):
        parts = parts[1:]  # only the location prefix: a field may itself be called "body"
    loc = ".".join(str(p) for p in parts)
    return JSONResponse(
        status_code=422,
        content={"detail": msg, "field": loc or None, "errors": jsonable(errors)},
    )


def jsonable(errors: list) -> list:
    out = []
    for e in errors:
        e = dict(e)
        e.pop("ctx", None)
        e.pop("input", None)
        out.append(e)
    return out


app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
