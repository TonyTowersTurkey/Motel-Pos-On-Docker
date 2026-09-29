"""Custom middleware for the motel occupancy Django application."""

import logging
import time
from typing import Any

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):  # type: ignore[misc]
    """Log all incoming HTTP requests with timing information.

    Adds request duration to the response headers and logs each request.
    """

    def process_request(self, request) -> Any | None:  # type: ignore[no-untyped-def]
        """Record start time of the request."""
        request._request_start_time = time.time()  # type: ignore[attr-defined]
        logger.info(
            "Request START: %s %s from %s",
            request.method,
            request.get_full_path(),
            request.META.get("REMOTE_ADDR", ""),  # type: ignore[attr-defined]
        )
        return None

    def process_response(self, request, response) -> Any:  # type: ignore[no-untyped-def]
        """Add duration header and log completion."""
        start_time: float = getattr(request, "_request_start_time", time.time())
        duration_ms: int = int((time.time() - start_time) * 1000)
        response["X-Request-Duration"] = str(duration_ms)
        logger.info(
            "Request END: %s %s -> %d in %dms",
            request.method,
            request.get_full_path(),
            response.status_code,
            duration_ms,
        )
        return response
