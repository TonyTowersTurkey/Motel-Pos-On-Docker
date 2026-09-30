#!/bin/sh
set -eu

case "${1:-web}" in
  web)
    exec "/app/.venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
    ;;
  snapshot)
    exec "/app/.venv/bin/python" -m app.worker.detect_once
    ;;
  generate_crops)
    exec "/app/.venv/bin/python" -m app.worker.generate_training_crops
    ;;
  init)
    exec "/app/.venv/bin/python" -m app.db.init_db
    ;;
  *)
    exec "$@"
    ;;
esac
