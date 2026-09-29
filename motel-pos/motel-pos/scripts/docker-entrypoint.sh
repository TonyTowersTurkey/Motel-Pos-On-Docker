#!/bin/sh
set -eu

case "${1:-web}" in
    web)
        exec uvicorn config.asgi:application \
            --host 0.0.0.0 \
            --port "${PORT:-8000}" \
            --workers "${WEB_CONCURRENCY:-4}" \
            --proxy-headers \
            --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
            --timeout-graceful-shutdown "${GRACEFUL_SHUTDOWN_TIMEOUT:-30}"
        ;;
    init)
        python manage.py migrate --noinput
        python manage.py collectstatic --noinput --clear
        ;;
    check)
        exec python manage.py check --deploy
        ;;
    *)
        exec "$@"
        ;;
esac
