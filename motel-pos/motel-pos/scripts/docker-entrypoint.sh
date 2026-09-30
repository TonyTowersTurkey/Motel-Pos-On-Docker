#!/bin/sh
set -eu

case "${1:-web}" in
    web)
        exec "/app/.venv/bin/python" -m uvicorn config.asgi:application \
            --host 0.0.0.0 \
            --port "${PORT:-8000}" \
            --workers "${WEB_CONCURRENCY:-4}" \
            --proxy-headers \
            --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
            --timeout-graceful-shutdown "${GRACEFUL_SHUTDOWN_TIMEOUT:-30}"
        ;;
    init)
        "/app/.venv/bin/python" manage.py migrate --noinput
        "/app/.venv/bin/python" manage.py collectstatic --noinput --clear
        ;;
    check)
        exec "/app/.venv/bin/python" manage.py check --deploy
        ;;
    *)
        exec "$@"
        ;;
esac
