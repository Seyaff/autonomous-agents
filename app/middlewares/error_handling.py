import time
import uuid
import logging
from typing import Callable

from fastapi import Request, Response, FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start_time = time.time()
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - START",
            extra={"request_id": request_id, "method": request.method, "path": request.url.path},
        )

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(process_time * 1000, 2),
                },
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.exception(
                f"[{request_id}] {request.method} {request.url.path} - ERROR ({process_time:.3f}s): {e}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(process_time * 1000, 2),
                },
            )
            raise


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])

    logger.exception(
        f"[{request_id}] Unhandled exception: {exc}",
        extra={"request_id": request_id, "path": request.url.path},
    )

    status_code = 500
    detail = "Internal server error"

    if hasattr(exc, "status_code"):
        status_code = exc.status_code
        detail = str(exc.detail) if hasattr(exc, "detail") else str(exc)

    return JSONResponse(
        status_code=status_code,
        content={
            "error": True,
            "message": detail,
            "request_id": request_id,
            "path": str(request.url.path),
        },
    )


def setup_error_handling(app: FastAPI) -> None:
    app.add_middleware(RequestLoggingMiddleware)
    app.add_exception_handler(Exception, global_exception_handler)