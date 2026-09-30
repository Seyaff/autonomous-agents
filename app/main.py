import os
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
    await verify_webhook_indexes()
    
    # Connect Redis in background (non-blocking for health checks)
    import asyncio
    asyncio.create_task(connect_redis_database_safe())
    
    yield
    # Shutdown
    await close_redis_connection()
    await close_mongo_connection()


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
