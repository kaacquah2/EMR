# MedSync — Deployment Runbook

Quick reference for hospital IT and DevOps. Full operations: [OPERATIONS_RUNBOOK.md](../medsync-backend/docs/OPERATIONS_RUNBOOK.md) (backend).

## Prerequisites

- PostgreSQL 16+ (Neon or self-hosted)
- Redis 7+ with password/TLS in production
- GitHub Secrets: `DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `AUDIT_LOG_SIGNING_KEY`, `DATABASE_URL`, `REDIS_URL`, `RAILWAY_TOKEN`, optional `VERCEL_TOKEN`

## Docker (on-prem or VM)

```bash
cp medsync-backend/.env.example medsync-backend/.env
# Edit .env — never use example keys in production

docker compose up -d --build
docker compose exec backend python manage.py setup_production
```

Backend image runs **Daphne** as user `medsync` (UID 1000). Static files are collected at image build time.

## Railway

1. Link repo; Railway reads [`railway.toml`](../railway.toml).
2. Set all production env vars in the Railway dashboard.
3. `preDeployCommand` runs `migrate --noinput` automatically.
4. On merge to `main`/`staging`, GitHub Actions runs `railway up` when `RAILWAY_TOKEN` is set.

## Nginx + TLS

Copy [`deploy/nginx/medsync.conf`](../deploy/nginx/medsync.conf) and [`deploy/nginx/proxy_params`](../deploy/nginx/proxy_params) to `/etc/nginx/`. Update `server_name` and certificate paths.

## Celery supervision

For VMs without Railway worker services, use [`deploy/celery/supervisord.conf`](../deploy/celery/supervisord.conf).

## Pre-go-live

Complete [GO_NO_GO_CHECKLIST.md](GO_NO_GO_CHECKLIST.md) Tier 1 (Blocking) before any real PHI.

## Health checks

- Liveness: `GET /api/v1/health` (fast)
- Deep: `GET /api/v1/health?deep=true` (Redis, audit chain, backup status)

Backup reports `not_configured` until `BACKUP_ENABLED=true` and a successful run is recorded via `api.services.backup_status.record_backup_success()`.
