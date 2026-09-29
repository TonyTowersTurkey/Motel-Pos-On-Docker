"""WSGI entry point (fallback) for motel occupancy Django project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()  # type: ignore[name-defined]
