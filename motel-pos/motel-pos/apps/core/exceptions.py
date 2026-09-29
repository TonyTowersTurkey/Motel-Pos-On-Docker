"""Shared exception handler for DRF."""

import logging

from rest_framework.exceptions import APIException, ValidationError

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict) -> dict | None:  # type: ignore[type-arg]
    """Custom DRF exception handler producing consistent JSON error responses.

    Args:
        exc: The raised exception instance.
        context: The view/context that raised the exception.

    Returns:
        Dict response if the exception should be handled, None to fall through.
    """
    from rest_framework.response import Response
    from rest_framework.status import (
        HTTP_400_BAD_REQUEST,
        HTTP_500_INTERNAL_SERVER_ERROR,
    )

    if isinstance(exc, ValidationError):
        errors = []
        if isinstance(exc.detail, dict):
            for field, messages in exc.detail.items():  # type: ignore[union-attr]
                if isinstance(messages, list):
                    for message in messages:
                        errors.append(
                            {
                                "code": getattr(message, "code", ""),
                                "detail": str(message),
                                "attr": field,
                            }
                        )
                else:
                    errors.append(
                        {
                            "code": "",
                            "detail": str(messages),
                            "attr": field,
                        }
                    )
        elif isinstance(exc.detail, list):
            for item in exc.detail:  # type: ignore[union-attr]
                errors.append(
                    {
                        "code": getattr(item, "code", ""),
                        "detail": str(item),
                        "attr": "",
                    }
                )

        return Response(
            {
                "type": "validation_error",
                "errors": errors,
            },
            status=HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, APIException):
        error_type = (
            "authentication_error"
            if exc.status_code and exc.status_code < 400
            else ("permission_error" if exc.status_code == 403 else "api_error")
        )
        return Response(
            {
                "type": error_type,
                "message": str(exc.detail),
                "status_code": exc.status_code,
            },
            status=exc.status_code,
        )

    # Catch-all for unexpected exceptions - never expose stack traces
    logger.exception(
        "Unhandled API exception in %s",
        context.get("view", context.get("request", "unknown view")),
        exc_info=exc,
    )
    return Response(
        {
            "type": "internal_error",
            "message": "An unexpected error occurred.",
        },
        status=HTTP_500_INTERNAL_SERVER_ERROR,
    )
