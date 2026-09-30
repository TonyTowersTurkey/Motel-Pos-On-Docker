# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.12.5 AS uv

FROM python:3.12-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /build

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev pkg-config

COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH \
    PORT=8000 \
    WEB_CONCURRENCY=4

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends curl libpq5 && \
    groupadd --gid 10001 motel-pos && \
    useradd --uid 10001 --gid motel-pos --create-home --home-dir /home/motel-pos motel-pos

COPY --from=builder /build/.venv /app/.venv
COPY --chown=motel-pos:motel-pos pyproject.toml manage.py main.py ./
COPY --chown=motel-pos:motel-pos apps/ ./apps/
COPY --chown=motel-pos:motel-pos config/ ./config/
COPY --chown=motel-pos:motel-pos templates/ ./templates/
COPY --chown=motel-pos:motel-pos scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint

RUN mkdir -p /app/staticfiles /app/media /app/data/reports && \
    chown -R motel-pos:motel-pos /app/staticfiles /app/media /app/data && \
    chmod 0755 /usr/local/bin/docker-entrypoint

USER motel-pos

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8000/api/health/ >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint"]
CMD ["web"]
