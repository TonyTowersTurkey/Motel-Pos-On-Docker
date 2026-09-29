"""Production configuration validation tests."""

from django.test import SimpleTestCase
from pydantic import ValidationError

from config.settings import Settings


class DeploymentSettingsTest(SimpleTestCase):
    def test_production_rejects_missing_secret_key(self) -> None:
        with self.assertRaisesRegex(ValidationError, "SECRET_KEY is required"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
                SECRET_KEY="",
            )

    def test_valid_production_configuration_uses_redis(self) -> None:
        production = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            DEBUG=False,
            SECRET_KEY="a-strong-production-secret-key-with-more-than-fifty-characters",  # noqa: S106
            ALLOWED_HOSTS="motel-pos.example.internal",
            CSRF_TRUSTED_ORIGINS="https://motel-pos.example.internal",
            ROOM_PULSE_WEBHOOK_TOKEN="a-room-pulse-token-longer-than-thirty-two-characters",  # noqa: S106
            DB_PASSWORD="a-strong-database-password",  # noqa: S106
            REDIS_REQUIRED=True,
            SSE_REDIS_URL="redis://redis:6379/2",
        )

        self.assertEqual(
            production.CACHES["default"]["BACKEND"],
            "django_redis.cache.RedisCache",
        )
