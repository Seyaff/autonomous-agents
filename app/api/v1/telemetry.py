from fastapi import APIRouter
from app.services.telemetry_service import telemetry_service

router = APIRouter(prefix="/telemetry", tags=["Observability & Tracing"])

@router.get("/metrics")
async def get_metrics():
    """
    Returns high-level turn metrics: total turns, audio percentage, p95 latency, error rate.
    """
    return telemetry_service.get_summary_metrics()

@router.get("/traces")
async def get_recent_traces(limit: int = 50):
    """
    Returns recent turn execution traces with granular span timings (ASR, LLM, DB, Meta API).
    """
    return {
        "metrics": telemetry_service.get_summary_metrics(),
        "traces": telemetry_service.get_recent_traces(limit=limit),
    }
