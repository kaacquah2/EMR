#!/usr/bin/env bash
# Railway / Railpack: run ASGI server for medsync-backend (Django + Channels).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/medsync-backend"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-medsync_backend.settings}"
PORT="${PORT:-8000}"
python manage.py migrate --noinput
exec daphne -b 0.0.0.0 -p "$PORT" medsync_backend.asgi:application
