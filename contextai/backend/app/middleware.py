"""Middleware stack for ContextAI backend.

Includes:
  - CorrelationMiddleware: Adds X-Request-ID header for request tracing
  - ErrorReportingMiddleware: Catches unhandled exceptions and logs to SQLite
"""

import uuid
import time
import logging
import traceback
from datetime import datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("contextai.middleware")


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Assigns a unique X-Request-ID to every request for tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.time()

        response = await call_next(request)

        duration_ms = round((time.time() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        logger.info(
            f"[{request_id}] {request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)"
        )
        return response


class ErrorReportingMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions and logs them to the error_log SQLite table."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = getattr(request.state, "request_id", "unknown")
            tb = traceback.format_exc()
            logger.error(f"[{request_id}] Unhandled error: {exc}")

            # Write to SQLite error log
            try:
                _log_error_to_db(
                    request_id=request_id,
                    method=request.method,
                    path=str(request.url.path),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    traceback_text=tb,
                )
            except Exception:
                pass  # Don't let error logging crash the error handler

            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                },
            )


def _log_error_to_db(
    request_id: str,
    method: str,
    path: str,
    error_type: str,
    error_message: str,
    traceback_text: str,
):
    """Insert an error record into the error_log table."""
    from app.db import get_db

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO error_log (request_id, method, path, error_type, error_message, traceback, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                request_id,
                method,
                path,
                error_type,
                error_message[:2000],
                traceback_text[:5000],
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
