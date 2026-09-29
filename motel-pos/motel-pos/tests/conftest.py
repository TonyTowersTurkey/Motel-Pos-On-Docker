"""Global pytest fixtures and configuration for motel occupancy Django tests."""

import os
import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pytest_configure(config):  # type: ignore[no-untyped-def]
    """Configure pytest for Django test discovery."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django  # noqa: PLC0415

    django.setup()
