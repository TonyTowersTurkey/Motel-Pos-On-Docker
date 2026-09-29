"""ASGI entry point for Django HTTP traffic and the authenticated SSE stream."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_application = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import URLRouter  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler  # noqa: E402
from django.urls import path  # noqa: E402

from apps.core.consumers import DashboardEventsConsumer  # noqa: E402

sse_application = AuthMiddlewareStack(
    URLRouter([path("api/events/stream/", DashboardEventsConsumer.as_asgi())])
)


async def protocol_application(scope, receive, send):  # type: ignore[no-untyped-def]
    """Route only the event stream through Channels; keep normal HTTP in Django."""
    if scope["type"] == "http" and scope.get("path") == "/api/events/stream/":
        await sse_application(scope, receive, send)
        return
    await django_application(scope, receive, send)


# Uvicorn does not add Django's development static-file handler like runserver does.
# Keep production static delivery with the reverse proxy by enabling this only in debug.
application = (
    ASGIStaticFilesHandler(protocol_application)
    if settings.DEBUG
    else protocol_application
)
