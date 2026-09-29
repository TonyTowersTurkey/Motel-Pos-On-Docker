"""Tests for shared core health endpoints."""

from unittest.mock import MagicMock, patch
from uuid import UUID

from django.core.cache import cache
from django.test import TestCase, override_settings


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "healthcheck-test-cache",
        }
    }
)
class HealthcheckViewTest(TestCase):
    """Health endpoint should probe cache without clearing app data."""

    def test_healthcheck_preserves_existing_cache_keys(self) -> None:
        cache_key = "healthcheck:cache-ping:00000000000000000000000000000001"
        cache.set("cashier:room-summary", {"occupied": 3}, timeout=60)

        with patch(
            "apps.core.healthcheck.uuid.uuid4",
            return_value=UUID("00000000-0000-0000-0000-000000000001"),
        ):
            response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["db"], "ok")
        self.assertEqual(payload["cache"], "ok")
        self.assertEqual(cache.get("cashier:room-summary"), {"occupied": 3})
        self.assertIsNone(cache.get(cache_key))

    def test_healthcheck_reports_unhealthy_when_cache_ping_fails(self) -> None:
        failing_cache = MagicMock()
        failing_cache.set.side_effect = RuntimeError("cache unavailable")
        failing_cache.delete.return_value = None

        with patch("apps.core.healthcheck.caches") as mock_caches:
            mock_caches.__getitem__.return_value = failing_cache
            response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "unhealthy")
        self.assertEqual(payload["db"], "ok")
        self.assertEqual(payload["cache"], "error")

    def test_healthcheck_stays_healthy_if_cleanup_delete_fails(self) -> None:
        cache.set("cashier:room-summary", {"occupied": 3}, timeout=60)

        with patch.object(cache, "delete", side_effect=RuntimeError("cleanup failed")):
            with patch(
                "apps.core.healthcheck.uuid.uuid4",
                return_value=UUID("00000000-0000-0000-0000-000000000001"),
            ):
                response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["db"], "ok")
        self.assertEqual(payload["cache"], "ok")
        self.assertEqual(cache.get("cashier:room-summary"), {"occupied": 3})
