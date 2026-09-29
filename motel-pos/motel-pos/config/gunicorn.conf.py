"""Gunicorn configuration for ASGI deployment.

Usage: gunicorn config.asgi:application -c config/gunicorn.conf.py
"""

import multiprocessing

# ASGI worker class
worker_class = "uvicorn.workers.UvicornWorker"

# Workers = (2 * CPU cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1

# Binding
bind = "0.0.0.0:8000"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Timeouts
timeout = 120
graceful_timeout = 30
keepalive = 5

# Security
limit_request_line = 8190
limit_request_fields = 100
