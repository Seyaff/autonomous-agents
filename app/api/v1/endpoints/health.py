import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import PyMongoError
from redis.exceptions import RedisError

from core.database import get_database, get_redis
from core.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
@router.get("/")
async def health_check() -> Dict[str, str]:
    """Liveness probe - returns 200 if service is running"""
    return {"status": "alive", "service": "whatsapp-agent"}


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Readiness probe - checks all dependencies"""
    checks = {
        "mongodb": "unknown",
        "redis": "unknown",
        "pinecone": "unknown",
    }
    overall_healthy = True

    # Check MongoDB
    try:
        db = get_database()
        await db.command("ping")
        checks["mongodb"] = "healthy"
    except PyMongoError as e:
        checks["mongodb"] = f"unhealthy: {e}"
        overall_healthy = False
    except RuntimeError as e:
        checks["mongodb"] = f"not_initialized: {e}"
        overall_healthy = False

    # Check Redis
    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "healthy"
    except RedisError as e:
        checks["redis"] = f"unhealthy: {e}"
        overall_healthy = False
    except RuntimeError as e:
        checks["redis"] = f"not_initialized: {e}"
        overall_healthy = False

    # Check Pinecone (just verify API key is configured)
    try:
        if settings.PINECONE_API_KEY:
            checks["pinecone"] = "configured"
        else:
            checks["pinecone"] = "not_configured"
            overall_healthy = False
    except Exception as e:
        checks["pinecone"] = f"error: {e}"
        overall_healthy = False

    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if overall_healthy else "not_ready",
        "checks": checks,
    }


@router.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """Basic metrics for monitoring"""
    try:
        db = get_database()
        tenants_count = await db["tenants"].count_documents({})
        orders_count = await db["orders"].count_documents({})
        profiles_count = await db["customer_profiles"].count_documents({})
        summaries_count = await db["conversation_summaries"].count_documents({})

        return {
            "tenants": tenants_count,
            "orders": orders_count,
            "customer_profiles": profiles_count,
            "conversation_summaries": summaries_count,
        }
    except Exception as e:
        logger.exception(f"Metrics collection failed: {e}")
        raise HTTPException(status_code=500, detail="Metrics unavailable")