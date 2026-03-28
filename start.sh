#!/usr/bin/env bash
# Railway / Railpack: run ASGI server for medsync-backend (Django + Channels).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/medsync-backend"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-medsync_backend.settings}"
PORT="${PORT:-8000}"

if [ -z "${SECRET_KEY:-}" ]; then
  echo "ERROR: SECRET_KEY is not set. Railway: open your service → Variables → New Variable" >&2
  echo "  Name: SECRET_KEY   Value: output of: openssl rand -hex 32" >&2
  echo "  Also set DATABASE_URL (Postgres), ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS for production." >&2
  exit 1
fi

python manage.py migrate --noinput
exec daphne -b 0.0.0.0 -p "$PORT" medsync_backend.asgi:application
