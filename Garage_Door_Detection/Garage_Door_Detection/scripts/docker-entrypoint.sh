#!/bin/sh
set -eu

case "${1:-web}" in
  web)
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
    ;;
  snapshot)
    exec python -m app.worker.detect_once
    ;;
  generate_crops)
    exec python -m app.worker.generate_training_crops
    ;;
  init)
    exec python -m app.db.init_db
    ;;
  *)
    exec "$@"
    ;;
esac
