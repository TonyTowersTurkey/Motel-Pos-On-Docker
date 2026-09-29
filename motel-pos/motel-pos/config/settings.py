"""
Django settings for motel occupancy Django project.

Configuration is driven by pydantic-settings reading from .env file.
"""

import socket
from pathlib import Path

from django.core.management.utils import get_random_secret_key
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

BASE_DIR: Path = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # Application name
    APP_NAME: str = "Motel Occupancy Django"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = ""
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    CSRF_TRUSTED_ORIGINS: str = ""
    ROOM_PULSE_WEBHOOK_TOKEN: str = ""
    ROOM_PULSE_REQUIRE_HTTPS: bool = True

    # Database - defaults to SQLite for local dev, PostgreSQL in production
    DB_ENGINE: str = "django.db.backends.postgresql"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "myproject_dev"
    DB_USER: str = "myproject_user"
    DB_PASSWORD: str = "motelpos"  # noqa: S105

    @property
    def DATABASES(self) -> dict[str, dict[str, object]]:  # noqa: N802
        """Build Django database config from settings."""
        return {
            "default": {
                "ENGINE": self.DB_ENGINE,
                "NAME": self.DB_NAME,
                "USER": self.DB_USER,
                "PASSWORD": self.DB_PASSWORD,
                "HOST": self.DB_HOST,
                "PORT": str(self.DB_PORT),
            }
        }

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_REQUIRED: bool = False
    SSE_REDIS_URL: str = ""

    @property
    def CACHES(self) -> dict[str, dict[str, object]]:  # noqa: N802
        """Build Django cache config from settings. Falls back to LocMem if Redis unavailable."""
        if self.REDIS_REQUIRED:
            redis_available = True
        else:
            try:
                sock = socket.create_connection(
                    (self.REDIS_HOST, self.REDIS_PORT), timeout=2
                )
                sock.close()
                redis_available = True
            except OSError:
                redis_available = False

        if redis_available:
            return {
                "default": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1",
                    "OPTIONS": {
                        "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    },
                }
            }
        # Fallback to in-memory cache when Redis is not available
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "motel-cache",
            }
        }

    # Auth
    AUTH_USER_MODEL: str = "users.User"
    AUTHENTICATION_BACKENDS: list[str] = Field(
        default_factory=lambda: [
            "django.contrib.auth.backends.ModelBackend",
        ]
    )

    # Security
    SECURE_HSTS_SECONDS: int = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS: bool = False
    SECURE_HSTS_PRELOAD: bool = False
    SECURE_SSL_REDIRECT: bool = True
    SESSION_COOKIE_SECURE: bool = True
    CSRF_COOKIE_SECURE: bool = True
    SECURE_CONTENT_TYPE_NOSNIFF: bool = True
    SECURE_REFERRER_POLICY: str = "same-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY: str = "same-origin"
    X_FRAME_OPTIONS: str = "DENY"
    SECURE_PROXY_SSL_HEADER: tuple[str, str] = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )

    # Logging level from environment
    LOG_LEVEL: str = "INFO"

    @property
    def LOGGING(self) -> dict[str, object]:  # noqa: N802
        """Build Django LOGGING dict with JSON formatter."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "fmt": "%(levelname)s %(name)s %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": self.LOG_LEVEL,
            },
        }

    # Static files
    STATIC_URL: str = "/static/"
    STATIC_ROOT: Path = BASE_DIR / "staticfiles"
    MEDIA_URL: str = "/media/"
    MEDIA_ROOT: Path = BASE_DIR / "media"
    REPORT_ROOT: Path = BASE_DIR / "data" / "reports"

    # Application server
    WEB_CONCURRENCY: int = Field(default=4, ge=1, le=32)

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":  # noqa: PLR0912
        """Fail early when a production container is missing critical settings."""
        if not self.SECRET_KEY:
            if self.ENVIRONMENT.lower() == "production":
                raise ValueError("SECRET_KEY is required in production")
            self.SECRET_KEY = get_random_secret_key()

        if self.ENVIRONMENT.lower() != "production":
            return self

        errors: list[str] = []
        if self.DEBUG:
            errors.append("DEBUG must be false")
        if len(self.SECRET_KEY) < 50:  # noqa: PLR2004
            errors.append("SECRET_KEY must contain at least 50 characters")
        if not self.ALLOWED_HOSTS.strip():
            errors.append("ALLOWED_HOSTS must not be empty")
        if not self.CSRF_TRUSTED_ORIGINS.strip():
            errors.append("CSRF_TRUSTED_ORIGINS must not be empty")
        if len(self.ROOM_PULSE_WEBHOOK_TOKEN) < 32:  # noqa: PLR2004
            errors.append(
                "ROOM_PULSE_WEBHOOK_TOKEN must contain at least 32 characters"
            )
        if not self.REDIS_REQUIRED:
            errors.append("REDIS_REQUIRED must be true")
        if not self.SSE_REDIS_URL:
            errors.append("SSE_REDIS_URL must be configured")
        if self.DB_PASSWORD in {"", "motelpos", "change-me"}:
            errors.append("DB_PASSWORD must be changed")
        if not self.SECURE_SSL_REDIRECT:
            errors.append("SECURE_SSL_REDIRECT must be true")
        if not self.SESSION_COOKIE_SECURE:
            errors.append("SESSION_COOKIE_SECURE must be true")
        if not self.CSRF_COOKIE_SECURE:
            errors.append("CSRF_COOKIE_SECURE must be true")
        if self.SECURE_HSTS_SECONDS <= 0:
            errors.append("SECURE_HSTS_SECONDS must be greater than zero")
        if errors:
            raise ValueError("Invalid production configuration: " + "; ".join(errors))
        return self

    # Template directories
    @property
    def TEMPLATES(self) -> list[dict[str, object]]:  # noqa: N802
        """Build Django templates config."""
        return [
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [BASE_DIR / "templates"],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                        "django.contrib.messages.context_processors.messages",
                    ],
                },
            }
        ]

    # Internationalization
    LANGUAGE_CODE: str = "en-us"
    TIME_ZONE: str = "America/Puerto_Rico"
    USE_I18N: bool = True
    USE_TZ: bool = True

    # Pricing tiers (ported from existing config)
    PRICING_TIERS: str = ""

    model_config = __import__("pydantic_settings").SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="allow",
    )


# Load settings from environment
settings = Settings()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = settings.DEBUG
ENVIRONMENT: str = settings.ENVIRONMENT
IS_PRODUCTION: bool = ENVIRONMENT.lower() == "production"
SECRET_KEY: str = settings.SECRET_KEY
ALLOWED_HOSTS: list[str] = [
    h.strip() for h in settings.ALLOWED_HOSTS.split(",") if h.strip()
]
CSRF_TRUSTED_ORIGINS: list[str] = [
    origin.strip()
    for origin in settings.CSRF_TRUSTED_ORIGINS.split(",")
    if origin.strip()
]
ROOM_PULSE_WEBHOOK_TOKEN: str = settings.ROOM_PULSE_WEBHOOK_TOKEN
ROOM_PULSE_REQUIRE_HTTPS: bool = settings.ROOM_PULSE_REQUIRE_HTTPS
SECURE_PROXY_SSL_HEADER: tuple[str, str] = settings.SECURE_PROXY_SSL_HEADER
USE_X_FORWARDED_HOST: bool = True
SECURE_HSTS_SECONDS: int = settings.SECURE_HSTS_SECONDS if IS_PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS: bool = settings.SECURE_HSTS_INCLUDE_SUBDOMAINS
SECURE_HSTS_PRELOAD: bool = settings.SECURE_HSTS_PRELOAD
SECURE_SSL_REDIRECT: bool = settings.SECURE_SSL_REDIRECT if IS_PRODUCTION else False
SESSION_COOKIE_SECURE: bool = settings.SESSION_COOKIE_SECURE if IS_PRODUCTION else False
CSRF_COOKIE_SECURE: bool = settings.CSRF_COOKIE_SECURE if IS_PRODUCTION else False
SECURE_CONTENT_TYPE_NOSNIFF: bool = settings.SECURE_CONTENT_TYPE_NOSNIFF
SECURE_REFERRER_POLICY: str = settings.SECURE_REFERRER_POLICY
SECURE_CROSS_ORIGIN_OPENER_POLICY: str = settings.SECURE_CROSS_ORIGIN_OPENER_POLICY
X_FRAME_OPTIONS: str = settings.X_FRAME_OPTIONS

# Application definition
INSTALLED_APPS: list[str] = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "drf_spectacular",
    "channels",
    # Local apps
    "apps.core",
    "apps.users",
    "apps.rooms",
    "apps.workorders",
    "apps.occupancy",
    "apps.revenue",
    "apps.guests",
    "apps.maintenance",
]

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF: str = "config.urls"

TEMPLATES: list[dict[str, object]] = settings.TEMPLATES

WSGI_APPLICATION: str = "config.wsgi.application"

ASGI_APPLICATION: str = "config.asgi.application"

# A single-process in-memory layer keeps local development self-contained.
# Production deployments must set SSE_REDIS_URL so events cross worker processes.
CHANNEL_LAYERS: dict[str, dict[str, object]] = {
    "default": (
        {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [settings.SSE_REDIS_URL]},
        }
        if settings.SSE_REDIS_URL
        else {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    )
}

# Database
DATABASES: dict[str, dict[str, object]] = settings.DATABASES

# Password validation
AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": ("django.contrib.auth.password_validation.MinimumLengthValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation.CommonPasswordValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation.NumericPasswordValidator"),
    },
]

# Internationalization
LANGUAGE_CODE: str = settings.LANGUAGE_CODE
TIME_ZONE: str = settings.TIME_ZONE
USE_I18N: bool = settings.USE_I18N
USE_TZ: bool = settings.USE_TZ
TIME_FORMAT = "H:i"
SHORT_TIME_FORMAT = "H:i"
DATETIME_FORMAT = "N j, Y, H:i"
SHORT_DATETIME_FORMAT = "m/d/Y H:i"

# Static files (CSS, JavaScript, Images)
STATIC_URL: str = settings.STATIC_URL
STATIC_ROOT: Path = settings.STATIC_ROOT
MEDIA_URL: str = settings.MEDIA_URL
MEDIA_ROOT: Path = settings.MEDIA_ROOT
REPORT_ROOT: Path = settings.REPORT_ROOT

# Default primary key field type
DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"

# Custom user model
AUTH_USER_MODEL: str = settings.AUTH_USER_MODEL
AUTHENTICATION_BACKENDS: list[str] = settings.AUTHENTICATION_BACKENDS
LOGIN_URL: str = "/login/"
LOGIN_REDIRECT_URL: str = "/manager/"
LOGOUT_REDIRECT_URL: str = "/login/"

# DRF configuration
REST_FRAMEWORK: dict[str, object] = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": ("apps.core.pagination.StandardPagination"),
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "room_pulse": "300/hour",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# Spectacular (OpenAPI) settings
SPECTACULAR_SETTINGS: dict[str, object] = {
    "TITLE": "Motel Occupancy API",
    "DESCRIPTION": (
        "Django REST Framework API for Motel Vehicle Occupancy Detection System"
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Logging
LOGGING: dict[str, object] = settings.LOGGING

# Reject unexpectedly large request bodies before parsing webhook JSON.
DATA_UPLOAD_MAX_MEMORY_SIZE: int = 1_048_576
