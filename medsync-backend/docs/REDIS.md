# Redis for MedSync (Celery broker / cache)

## Recommendation

| Environment | Use |
|-------------|-----|
| **Local development** | Redis on `localhost:6379` — easiest via Docker: `docker run -d -p 6379:6379 redis:7-alpine`. Matches production semantics without cost. |
| **Staging / production** | **Managed Redis** (AWS ElastiCache, GCP Memorystore, Azure Cache, Redis Cloud, Upstash, etc.) with TLS, persistence/replication where required, and automated patching. Avoid a single unmaintained VM unless you own backups and security. |

Configure `CELERY_BROKER_URL` or `REDIS_URL` in Django settings / `.env` so the health check at `GET /api/v1/health` can ping the same endpoint Celery uses.

## Why not “online only” for dev?

A local broker keeps Celery tasks working offline, avoids shared-dev race conditions, and removes network latency from the edit–run loop.
