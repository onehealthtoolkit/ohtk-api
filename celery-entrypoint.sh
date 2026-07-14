#!/bin/bash
# ohtk-api Celery worker entrypoint (no migrate, no ASGI)
set -euo pipefail

echo "start celery worker"
exec python -m celery -A podd_api worker -l info
