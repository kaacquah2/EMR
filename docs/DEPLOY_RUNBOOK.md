# MedSync — Deployment Runbook

Quick reference for hospital IT and DevOps. Full operations detail: [`medsync-backend/docs/OPERATIONS_RUNBOOK.md`](../medsync-backend/docs/OPERATIONS_RUNBOOK.md).

## Prerequisites

- PostgreSQL 16+ (Neon or self-hosted; use region `aws-af-south-1` / Africa/Cape Town for Ghana)
- GitHub Secrets: `DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `AUDIT_LOG_SIGNING_KEY`, `DATABASE_URL`
- Optional: `RAILWAY_TOKEN`, `VERCEL_TOKEN`, `SENTRY_DSN`

## Docker (on-prem or VM)

```bash
cp .env.docker .env.docker.local
# Edit — fill in ALL CHANGE_ME values. Startup will fail if any placeholder remains.
# Generate a secret:   python -c "import secrets; print(secrets.token_urlsafe(32))"
# Generate ADMIN_URL:  python -c "import secrets; print('ms-admin-' + secrets.token_hex(4) + '/')"

docker compose up -d --build
docker compose exec backend python manage.py setup_production
```

Backend runs **gunicorn WSGI** (4 workers) as user `medsync` (UID 1000). Static files are collected at image build time. No Celery or Redis services are required.

## Railway

1. Link repo; Railway reads [`railway.toml`](../railway.toml).
2. Set all production env vars in the Railway dashboard.
3. `preDeployCommand` runs `migrate --noinput` automatically.
4. On merge to `main`/`staging`, GitHub Actions runs `railway up` when `RAILWAY_TOKEN` is set.

## Nginx + TLS

Copy [`deploy/nginx/medsync.conf`](../deploy/nginx/medsync.conf) and [`deploy/nginx/proxy_params`](../deploy/nginx/proxy_params) to `/etc/nginx/`. Update `server_name` and certificate paths. TLS must terminate at Nginx — Django's `SECURE_SSL_REDIRECT` is enabled when `DEBUG=False`.

## No-show cron

The no-show auto-mark job runs as a plain management command scheduled via host cron or the `deploy/cron/` config:

```
*/15 * * * *  /app/.venv/bin/python /app/manage.py mark_no_shows
```

## Pre-go-live

Complete [GO_NO_GO_CHECKLIST.md](GO_NO_GO_CHECKLIST.md) Tier 1 items before processing any real patient PHI. Key open items: key rotation, TLS at proxy, `ADMIN_URL` env var, DB backup automation.

## Health checks

- Liveness: `GET /api/v1/health`
- Deep: `GET /api/v1/health?deep=true` (audit chain integrity, backup status)

Backup status reports `not_configured` until `BACKUP_ENABLED=true` and a successful run is recorded.
