#!/bin/bash
# ohtk-api container entrypoint (web process)
#
# Default: collectstatic → optional gated migrate → optional superuser → ASGI (daphne)
# Migrations do NOT run unless RUN_MIGRATIONS is truthy (1/true/yes/on).
# Shared staging/production should migrate out-of-band (migrate_schemas), not on every boot.
#
# Env:
#   RUN_MIGRATIONS=1          apply migrate_schemas --noinput before start
#   SKIP_COLLECTSTATIC=1      skip collectstatic
#   ASGI_HOST / ASGI_PORT     bind address (default 0.0.0.0:8000)
#   DJANGO_SUPERUSER_*        optional createsuperuser --noinput
#
# Extra CLI args replace the default server command (after prep steps):
#   docker run ... ohtk-api daphne -b 0.0.0.0 -p 8000 podd_api.asgi:application

set -euo pipefail

env_truthy() {
  case "${1:-}" in
    1|true|True|TRUE|yes|Yes|YES|on|On|ON) return 0 ;;
    *) return 1 ;;
  esac
}

if ! env_truthy "${SKIP_COLLECTSTATIC:-0}"; then
  echo "Collect static files"
  python manage.py collectstatic --noinput
else
  echo "Skipping collectstatic (SKIP_COLLECTSTATIC set)"
fi

if env_truthy "${RUN_MIGRATIONS:-0}"; then
  echo "RUN_MIGRATIONS enabled: applying migrate_schemas --noinput"
  # django-tenants: migrate public + tenant schemas
  python manage.py migrate_schemas --noinput
else
  echo "Skipping migrations (set RUN_MIGRATIONS=1 for lab/bootstrap; prefer out-of-band migrate for shared envs)"
fi

if [ -z "${DJANGO_SUPERUSER_USERNAME:-}" ] || [ -z "${DJANGO_SUPERUSER_PASSWORD:-}" ] || [ -z "${DJANGO_SUPERUSER_EMAIL:-}" ]; then
  echo "No superuser created (DJANGO_SUPERUSER_* not fully set)"
else
  echo "Creating superuser (idempotent where Django allows)"
  python manage.py createsuperuser --noinput \
    --username "${DJANGO_SUPERUSER_USERNAME}" \
    --email "${DJANGO_SUPERUSER_EMAIL}" || true
fi

if [ "$#" -gt 0 ]; then
  echo "Starting custom command: $*"
  exec "$@"
fi

ASGI_HOST="${ASGI_HOST:-0.0.0.0}"
ASGI_PORT="${ASGI_PORT:-8000}"
echo "Starting ASGI server (daphne) on ${ASGI_HOST}:${ASGI_PORT}"
exec daphne -b "${ASGI_HOST}" -p "${ASGI_PORT}" podd_api.asgi:application
