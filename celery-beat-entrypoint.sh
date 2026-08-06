#!/bin/bash
# ohtk-api Celery beat entrypoint (singleton scheduler — run exactly one replica)
set -euo pipefail

echo "start celery beat"
exec python -m celery -A podd_api beat -l info
