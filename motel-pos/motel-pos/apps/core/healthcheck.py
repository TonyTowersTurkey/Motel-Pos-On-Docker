"""Health check endpoint for container orchestration."""

import logging
import uuid
from contextlib import suppress

from django.core.cache import caches
from django.db import connections
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@api_view(["GET"])  # type: ignore[call-overload]
@permission_classes([AllowAny])
def healthcheck(request) -> Response:  # type: ignore[no-untyped-def]
    """Health check endpoint for Docker/Kubernetes probes.

    Checks database connectivity and Redis cache connectivity.

    Returns:
        HTTP 200 when healthy, 503 when unhealthy, with connection status details.
    """
    del request

    db_status = "ok"
    cache_status = "ok"

    # Check database connectivity
    try:
        db_conn = connections["default"]
        db_conn.cursor().execute("SELECT 1")
    except Exception:
        logger.exception("Database health check failed")
        db_status = "error"

    # Check cache connectivity without mutating unrelated runtime keys.
    cache_key = f"healthcheck:cache-ping:{uuid.uuid4().hex}"
    try:
        cache = caches["default"]
        try:
            cache.set(cache_key, "ok", timeout=10)
            if cache.get(cache_key) != "ok":
                raise RuntimeError("cache ping value mismatch")
        finally:
            with suppress(Exception):
                cache.delete(cache_key)
    except Exception:
        logger.exception("Cache health check failed")
        cache_status = "error"
    if db_status == "ok" and cache_status == "ok":
        return Response(
            {"status": "healthy", "db": "ok", "cache": "ok"},
            status=200,
        )

    return Response(
        {"status": "unhealthy", "db": db_status, "cache": cache_status},
        status=503,
    )


@api_view(["GET"])  # type: ignore[call-overload]
@permission_classes([AllowAny])
def readiness(request) -> Response:  # type: ignore[no-untyped-def]
    """Simplified readiness probe (just checks app is running).

    Returns:
        HTTP 200 when the application is responding to requests.
    """
    del request
    return Response({"ready": True}, status=200)
