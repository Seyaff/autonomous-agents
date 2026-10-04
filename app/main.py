import os
import sys

# Windows consoles default to a legacy codepage (cp1252) that can't encode
# the emoji used in several log/print lines throughout this app — without
# this, a single such line crashes app startup with UnicodeEncodeError.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from starlette.middleware.sessions import SessionMiddleware
from core.settings import settings
from fastapi.middleware.cors import CORSMiddleware

from core.database import (
    connect_to_mongo,
    close_mongo_connection,
    ensure_webhook_indexes,
    verify_webhook_indexes,
    connect_redis_database,
    close_redis_connection,
)
from middlewares.error_handling import setup_error_handling
from core.logging import configure_logging

from api.v1.routes import v1_router

load_dotenv()

configure_logging()


# Simple liveness check - no dependencies
from fastapi.responses import PlainTextResponse
from fastapi import Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - minimal blocking work
    # Connect to MongoDB (required)
    await connect_to_mongo()
    await ensure_webhook_indexes()
    _warn_if_google_callback_is_off_domain()
    await verify_webhook_indexes()
    
    # Connect Redis in background (non-blocking for health checks)
    import asyncio
    asyncio.create_task(connect_redis_database_safe())
    billing_task = asyncio.create_task(billing_scheduler())
    payments_task = asyncio.create_task(payment_expiry_loop())

    yield
    # Shutdown
    billing_task.cancel()
    payments_task.cancel()
    await close_redis_connection()
    await close_mongo_connection()


def _warn_if_google_callback_is_off_domain():
    """Google sign-in only works when the callback is on the same site as the app (the Vercel address).
    A callback on the API's own domain loses the sign-in state, and every Google sign-in fails."""
    import logging
    from core.settings import settings

    callback = settings.GOOGLE_CALLBACK_URL or ""
    frontend = (settings.FRONTEND_URL or "").rstrip("/")
    if settings.GOOGLE_CLIENT_ID and frontend and not callback.startswith(frontend):
        logging.getLogger(__name__).warning(
            f"[google] GOOGLE_CALLBACK_URL ({callback}) is not on the app's address ({frontend}). "
            f"Set it to {frontend}/api/auth/google/callback, and register that address in Google Cloud Console."
        )


async def payment_expiry_loop():
    """Every minute: order payment links that ran out are offered cash on delivery instead."""
    import asyncio
    import logging
    from core.database import get_database
    from services.online_payments import expire_stale_payments

    logger = logging.getLogger(__name__)
    await asyncio.sleep(30)
    while True:
        try:
            await expire_stale_payments(get_database())
        except Exception as e:
            logger.exception(f"[payments] expiry check failed: {e}")
        await asyncio.sleep(60)


async def billing_scheduler():
    """Runs the daily billing job: renewals, overdue invoices and cancellations."""
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    from core.database import get_database
    from services.renewals import run_billing_jobs

    await asyncio.sleep(120)  # let startup finish first
    while True:
        try:
            await run_billing_jobs(get_database())
        except Exception as e:
            logger.exception(f"[billing] daily job failed: {e}")
        await asyncio.sleep(24 * 60 * 60)


async def connect_redis_database_safe():
    """Connect to Redis without blocking startup."""
    try:
        from core.database import connect_redis_database
        await connect_redis_database()
    except Exception as e:
        print(f"[redis] Background connection failed: {e}")


app = FastAPI(
    title="Autonomous Agent Business Platform",
    description="Multi-tenant autonomous AI operating system for restaurant operations and founder growth.",
    version="1.0.0",
    lifespan=lifespan,
)

# Liveness probe - responds immediately without any dependencies
@app.get("/health/live")
async def liveness():
    return PlainTextResponse("OK", status_code=200)

setup_error_handling(app)

origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    settings.FRONTEND_ORIGIN,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
)


app.include_router(v1_router, prefix="/api/v1")
