import asyncio
import contextlib
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.services.email_outbox import process_email_outbox
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    broker.bind_loop(asyncio.get_running_loop())
    if settings.REALTIME_ENABLED:
        listener.start()
    tasks = []
    if settings.ENVIRONMENT != "test":
        tasks = [asyncio.create_task(_subscription_watcher()), asyncio.create_task(_email_outbox_worker())]
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


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return a readable first error message plus the full list."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    msg = str(first.get("msg", "Некорректные данные")).removeprefix("Value error, ")
    loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
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
