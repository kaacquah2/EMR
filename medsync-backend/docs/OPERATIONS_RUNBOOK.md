# MedSync Operations Runbook

**Purpose:** Quick troubleshooting guide for on-call operations and support teams.

**Version:** 1.0  
**Last Updated:** 2025

---

## Table of Contents

1. [Daily Health Checks](#daily-health-checks)
2. [Common Incidents](#common-incidents)
3. [Incident Response Flowchart](#incident-response-flowchart)
4. [Troubleshooting by Symptom](#troubleshooting-by-symptom)
5. [Performance Tuning](#performance-tuning)
6. [On-Call Procedures](#on-call-procedures)
7. [Monitoring & Alerting](#monitoring--alerting)
8. [Contact & Escalation](#contact--escalation)

---

## Daily Health Checks

### Pre-Shift Checklist (08:00 AM)

Run every morning before staff arrives:

```bash
# 1. Check API health
curl -s http://localhost:8000/api/v1/health | jq '.'

# Expected response:
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "ai_model": "loaded",
  "timestamp": "2025-01-15T08:00:00Z"
}

# 2. Check database connection
curl -s http://localhost:8000/api/v1/superadmin/system-health | jq '.components.database'

# Expected: {"status": "ok", "connection_pool": "12/20", "query_latency_ms": <50}

# 3. Check AI model status
curl -s http://localhost:8000/api/v1/ai/status | jq '.'

# Expected: {"ai_enabled": true, "last_model_updated": "2025-01-10T...", ...}

# 4. Check background task queue
curl -s http://localhost:8000/api/v1/tasks | jq '.pending_count'

# Expected: < 50 pending tasks

# 5. Check active user count
curl -s http://localhost:8000/api/v1/admin/audit-logs?limit=1 -H "Authorization: Bearer <admin_token>" | jq '.count'

# 6. Verify no critical alerts
curl -s http://localhost:8000/api/v1/superadmin/security/alerts -H "Authorization: Bearer <admin_token>" | jq '.critical'

# Expected: [] (empty array, no critical alerts)
```

**Action Items:**
- If any check fails, follow "Troubleshooting by Symptom" section
- Document findings in daily log
- Alert manager if any issue persists

### Hourly Monitoring (during business hours)

```bash
# Check error rate in logs
tail -100 /var/log/medsync/api.log | grep "ERROR\|CRITICAL" | wc -l

# Expected: < 5 errors per hour

# Check database connection pool
curl -s http://localhost:8000/api/v1/superadmin/system-health | jq '.components.database.connection_pool'

# Expected: Not at max capacity (e.g., 12/20, not 20/20)

# Check AI queue backlog
curl -s http://localhost:8000/api/v1/superadmin/system-health | jq '.components.ai_model.requests_queue'

# Expected: < 20 requests in queue

# Check cache hit rate
curl -s http://localhost:8000/api/v1/superadmin/system-health | jq '.components.cache.hit_rate'

# Expected: > 80%
```

---

## Common Incidents

### Incident #1: Database Connection Pool Exhausted

**Symptoms:**
- API returns `500 Internal Server Error` on random requests
- Logs show `OperationalError: QueuePool limit exceeded`
- Response times spike to > 10 seconds

**Root Causes:**
- Long-running report query consuming all connections
- Connection leak (not properly closed)
- Batch import with thousands of records
- AI model analysis generating many DB queries

**Verification Steps:**

```bash
# 1. Check pool status
curl -s http://localhost:8000/api/v1/superadmin/system-health | jq '.components.database'

# If pool is at max:
# 2. Check active queries
psql -U postgres -d medsync_db -c "SELECT query, state, query_start FROM pg_stat_activity WHERE query NOT LIKE '%pg_stat_activity%' ORDER BY query_start;"

# 3. Identify long-running query (> 5 minutes)
psql -U postgres -d medsync_db -c "SELECT pid, query, now() - query_start as duration FROM pg_stat_activity WHERE query_start < now() - interval '5 minutes';"
```

**Resolution Steps:**

1. **Kill the offending query:**
   ```bash
   # Get the PID from above query
   psql -U postgres -d medsync_db -c "SELECT pg_terminate_backend(PID);"
   ```

2. **Restart API to reset connection pool:**
   ```bash
   # If on Docker
   docker restart medsync-api
   
   # If systemd
   systemctl restart medsync-api
   ```

3. **Clear connection pool in Django:**
   ```bash
   # SSH into app server
   python manage.py shell
   >>> from django.db import connection
   >>> connection.close()
   ```

4. **Check pool recovered:**
   ```bash
   # Wait 30 seconds, then verify
   curl -s http://localhost:8000/api/v1/superadmin/system-health | jq '.components.database.connection_pool'
   # Should show lower number like "3/20"
   ```

**Prevention Measures:**
- Set `CONN_MAX_AGE=300` in Django settings (force connection recycling every 5 minutes)
- Add query timeout: `STATEMENT_TIMEOUT=30000` (30 seconds) in postgres config
- Monitor slow queries: Enable `log_min_duration_statement = 5000` in postgres
- Use connection pooling (PgBouncer) for production

---

### Incident #2: AI Model Disabled / Not Responding

**Symptoms:**
- `/api/v1/ai/status` returns `{"ai_enabled": false}`
- AI endpoints return `503 Service Unavailable`
- AI analysis jobs stuck in queue
- Logs show: `AI model failed to load` or `FAISS index corruption`

**Root Causes:**
- FAISS index file corrupted or deleted
- Model weights file not found or corrupted
- GPU/CUDA out of memory
- Model initialization timeout (> 5 minutes)
- Insufficient disk space for index

**Verification Steps:**

```bash
# 1. Check if AI model is loaded
curl -s http://localhost:8000/api/v1/ai/status | jq '.ai_enabled'

# 2. Check error logs
tail -50 /var/log/medsync/ai.log | grep -i "error\|warning"

# 3. Check disk space (if using FAISS index)
df -h /var/lib/medsync/models/

# Expected: > 10GB free space

# 4. Check GPU status (if using CUDA)
nvidia-smi

# Look for memory usage < 90%

# 5. Check model file integrity
ls -lh /var/lib/medsync/models/clinical_model* /var/lib/medsync/models/faiss*

# Files should exist and be > 100MB
```

**Resolution Steps:**

1. **Restart AI service:**
   ```bash
   # If containerized
   docker restart medsync-ai-service
   
   # If systemd
   systemctl restart medsync-ai-service
   ```

2. **Clear model cache:**
   ```bash
   # Remove stale cache files
   rm -rf /var/cache/medsync/ai_model_*
   redis-cli FLUSHDB  # Only if acceptable to clear Redis
   ```

3. **Verify GPU availability:**
   ```bash
   nvidia-smi
   # If no GPU available, check if using CPU fallback (slower but works)
   # Set env var: CUDA_VISIBLE_DEVICES=""
   ```

4. **Rebuild FAISS index (if corrupted):**
   ```bash
   python manage.py rebuild_faiss_index
   # This may take 10-30 minutes depending on patient data size
   ```

5. **Re-enable AI after restart:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/admin/ai/enable \
     -H "Authorization: Bearer <admin_token>" \
     -H "Content-Type: application/json" \
     -d '{"reason": "System restart - model reloaded"}'
   ```

6. **Verify recovery:**
   ```bash
   curl -s http://localhost:8000/api/v1/ai/status | jq '.ai_enabled'
   # Should return true
   ```

**Prevention Measures:**
- Monitor disk space: alert if < 15GB free on model directory
- Set up GPU memory monitoring: alert if > 95% used
- Daily FAISS index integrity check: `python manage.py check_faiss_integrity`
- Model health check every 6 hours

---

### Incident #3: High Database Query Latency (> 500ms)

**Symptoms:**
- API response times slow: 5-10 seconds for list endpoints
- Audit logs show query times > 500ms
- Patient search times out
- Dashboard metrics page slow to load

**Root Causes:**
- Missing database indexes
- N+1 query problem in Django ORM
- Large full table scan (millions of records without WHERE clause)
- Concurrent batch operations (import, export)
- Vacuum/analyze not running

**Verification Steps:**

```bash
# 1. Check slow query logs
psql -U postgres -d medsync_db -c "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# 2. Check if indexes exist
psql -U postgres -d medsync_db -c "SELECT schemaname, tablename, indexname FROM pg_indexes WHERE tablename LIKE 'patients_%' OR tablename LIKE 'records_%';"

# 3. Analyze query execution plan
psql -U postgres -d medsync_db -c "EXPLAIN ANALYZE SELECT * FROM patients_patient WHERE hospital_id='xxx' LIMIT 100;"

# Look for "Sequential Scan" (bad) vs "Index Scan" (good)

# 4. Check vacuum/analyze stats
psql -U postgres -d medsync_db -c "SELECT schemaname, tablename, last_vacuum, last_autovacuum FROM pg_stat_user_tables WHERE n_tup_ins + n_tup_upd + n_tup_del > 10000 ORDER BY last_vacuum DESC LIMIT 10;"
```

**Resolution Steps:**

1. **Run immediate VACUUM ANALYZE:**
   ```bash
   psql -U postgres -d medsync_db -c "VACUUM ANALYZE;"
   # Takes 5-15 minutes depending on database size
   ```

2. **Create missing indexes:**
   ```bash
   psql -U postgres -d medsync_db < /app/sql/create_indexes.sql
   
   # Example indexes (if not present):
   CREATE INDEX CONCURRENTLY idx_patient_hospital ON patients_patient(hospital_id);
   CREATE INDEX CONCURRENTLY idx_medical_record_patient ON records_medicalrecord(patient_id);
   CREATE INDEX CONCURRENTLY idx_vital_encounter ON records_vital(encounter_id);
   ```

3. **Fix N+1 queries in code:**
   ```python
   # BAD: causes N+1 queries
   patients = Patient.objects.all()
   for p in patients:
       print(p.registered_at.name)  # queries DB for each patient!
   
   # GOOD: uses select_related
   patients = Patient.objects.select_related('registered_at').all()
   for p in patients:
       print(p.registered_at.name)  # no extra queries
   ```

4. **Optimize slow queries:**
   - Add WHERE clause to filter by hospital_id
   - Limit result set size (pagination)
   - Use select_related() / prefetch_related() in Django ORM

5. **Enable query logging in Django:**
   ```python
   # settings.py
   LOGGING = {
       'loggers': {
           'django.db.backends': {
               'handlers': ['console'],
               'level': 'DEBUG',  # Log all queries
           }
       }
   }
   
   # Then check slow queries:
   grep "duration" /var/log/medsync/django.log | grep -E "[0-9]{4}ms" | sort -k2 -rn | head -20
   ```

**Prevention Measures:**
- Run `VACUUM ANALYZE` nightly (schedule in cron)
- Monitor query performance: set slow_query_log threshold = 100ms
- Add APM (Application Performance Monitoring) tool: New Relic, Datadog, or Prometheus
- Code review: check for N+1 queries before merging
- Load test before production: simulate concurrent users

---

### Incident #4: Authentication Failures / 401 Errors Spike

**Symptoms:**
- Users report "Invalid token" errors
- Spike in 401 responses in logs
- Token refresh endpoint overloaded
- Frontend repeatedly getting 401 and retrying

**Root Causes:**
- Token blacklist expired prematurely
- JWT secret key rotated (new tokens not accepted)
- Token cache cleared unintentionally
- MFA session timeout too short
- Clock skew between servers

**Verification Steps:**

```bash
# 1. Check token blacklist status
redis-cli KEYS "blacklist:*" | wc -l
# Expected: < 100,000 entries

# 2. Check JWT secret key
python manage.py shell
>>> from django.conf import settings
>>> print(settings.SECRET_KEY)  # Should be consistent across all instances

# 3. Check server time
date
# Should match within 1 second across all servers

# 4. Check Redis availability
redis-cli PING
# Expected: PONG

# 5. Monitor token refresh rate
tail -100 /var/log/medsync/api.log | grep "auth/refresh" | wc -l
# Expected: < 10 per minute (unless many users refreshing)
```

**Resolution Steps:**

1. **Clear expired tokens from blacklist:**
   ```bash
   redis-cli
   > EVAL "return redis.call('DEL', unpack(redis.call('KEYS', ARGV[1])))" 0 "blacklist:*"
   # This removes all blacklisted tokens (aggressive approach)
   ```

2. **Verify JWT configuration:**
   ```bash
   python manage.py shell
   >>> from rest_framework_simplejwt.settings import DEFAULTS
   >>> print(DEFAULTS)
   
   # Check these values:
   # ACCESS_TOKEN_LIFETIME: 15 minutes (900 seconds) is typical
   # REFRESH_TOKEN_LIFETIME: 7 days is typical
   ```

3. **Sync server clocks:**
   ```bash
   # On each server
   ntpdate -s time.nist.gov
   # Or use systemd-timesyncd
   systemctl restart systemd-timesyncd
   ```

4. **Restart auth service:**
   ```bash
   docker restart medsync-api
   # Or
   systemctl restart medsync-api
   ```

5. **Force logout all users (emergency only):**
   ```bash
   redis-cli FLUSHDB  # Clears all tokens (AGGRESSIVE!)
   # Users must re-login from all devices
   ```

6. **Monitor recovery:**
   ```bash
   # Watch for 401 errors
   tail -f /var/log/medsync/api.log | grep "401\|token"
   
   # Should decrease to normal rate within 5 minutes
   ```

**Prevention Measures:**
- Sync all servers to NTP: configure `/etc/ntp.conf` or enable chrony
- Monitor token refresh rate: alert if > 50 per minute (user churn indicator)
- Test JWT secret key rotation: keep old key in config for 24 hours during transition
- Token blacklist cleanup: run weekly job to remove expired tokens
- Monitor Redis memory: alert if > 80% used

---

### Incident #5: High CPU / Memory Usage

**Symptoms:**
- API processes using 90%+ CPU
- Memory usage growing continuously (memory leak)
- Slow response times / timeouts
- System load > number of CPU cores

**Root Causes:**
- Unbounded loop in background task
- Memory leak in AI model inference
- Too many concurrent requests
- Batch operation processing too large dataset
- Cache not evicting old entries

**Verification Steps:**

```bash
# 1. Check process-level CPU/memory
top -p $(pgrep -f "python manage.py")
# OR
docker stats medsync-api

# 2. Check system resources
free -h  # Memory usage
df -h    # Disk space
ps aux | grep python | grep -v grep

# 3. Check Django memory usage by component
python manage.py shell
>>> import psutil
>>> p = psutil.Process()
>>> print(f"Memory: {p.memory_info().rss / 1024 / 1024}MB")

# 4. Check Redis memory (cache)
redis-cli INFO memory | grep used_memory_human

# Expected: < 2GB typically

# 5. Check for memory leaks in logs
grep "MemoryError\|memory\|OOM" /var/log/medsync/api.log

# 6. Check background task queue
celery -A medsync_backend inspect active | jq '.[]'

# See if tasks are stuck/not completing
```

**Resolution Steps:**

1. **Identify the culprit process:**
   ```bash
   ps aux | sort -k3 -rn | head -5  # Sort by CPU %
   ps aux | sort -k4 -rn | head -5  # Sort by MEM %
   ```

2. **Kill resource-hogging process (carefully):**
   ```bash
   # Get PID
   kill -9 <PID>
   
   # If it's celery task, kill just that task
   celery -A medsync_backend revoke <task_id> --terminate
   ```

3. **Check and kill stuck batch operations:**
   ```bash
   # If batch import is causing issue
   curl -X POST http://localhost:8000/api/v1/batch-import/<job_id>/cancel \
     -H "Authorization: Bearer <admin_token>"
   ```

4. **Restart service if memory pressure critical:**
   ```bash
   docker restart medsync-api
   # Or systemctl restart medsync-api
   ```

5. **Clear cache if Redis is bloated:**
   ```bash
   redis-cli
   > INFO memory  # Check before
   > FLUSHDB      # Clear cache (affects performance temporarily)
   > INFO memory  # Check after
   ```

6. **Monitor memory trend:**
   ```bash
   # Log memory usage every 5 minutes
   watch -n 300 'free -h >> /tmp/memory.log'
   
   # Check if growing
   tail -20 /tmp/memory.log
   ```

**Prevention Measures:**
- Set memory limits on containers: `--memory=4G --memory-swap=4G`
- Enable memory profiling in production: use memory_profiler
- Monitor memory trend: alert if growing > 10MB/hour (leak indicator)
- Clean up cache regularly: Redis MAXMEMORY eviction policy = `allkeys-lru`
- Profile AI model memory usage: limit batch size for inference

---

---

## Incident Response Flowchart

```
START: Alert received / Issue detected
  ↓
Is system healthy (API responding, DB connected)?
  ├─ YES → Is user experience impacted?
  │         ├─ NO → Investigate for root cause, document, monitor
  │         └─ YES → Check "Common Incidents" section
  │
  └─ NO → Check Health Endpoints
          ├─ API down → Restart service (Incident #1 resolution step 2)
          ├─ DB down → See "Database Issues" section
          ├─ AI down → See Incident #2
          └─ Redis down → redis-cli PING, restart if needed
          
Impact Assessment:
  ├─ Critical (patient care affected) → Page on-call manager immediately
  ├─ High (service degraded) → Alert engineering team
  └─ Medium/Low → Create ticket, resolve in next 4 hours

Root Cause Analysis:
  1. Gather logs: check /var/log/medsync/ for last 30 minutes
  2. Check metrics: CPU, memory, DB queries, error rates
  3. Review recent changes: git log --oneline --since="4 hours ago"
  4. Check external services: Database, Redis, Celery status
  5. Review incident database for similar issues

Resolution:
  1. Apply immediate fix (restart, kill process, etc.)
  2. Monitor metric recovery (should see improvement within 5 min)
  3. Verify user experience restored
  4. Document incident: what happened, root cause, fix, prevention

Escalation Path:
  Level 1: On-call engineer (tries common fixes)
  Level 2: Senior engineer (30 min if not resolved)
  Level 3: Engineering manager (1 hour if not resolved)
  Level 4: CTO (2 hours, critical incidents only)
```

---

## Troubleshooting by Symptom

### "502 Bad Gateway" / API Not Responding

```bash
# 1. Check if API process is running
ps aux | grep "python manage.py"

# If not running:
docker start medsync-api
# Or
systemctl start medsync-api

# 2. Check if API is listening on port 8000
netstat -tulpn | grep 8000
# OR
lsof -i :8000

# If not listening, check logs:
docker logs medsync-api | tail -50
# OR
journalctl -u medsync-api -n 50

# 3. If logs show import errors or syntax errors, check recent deployments
git log --oneline -5
git diff HEAD~1  # See what changed

# 4. If database error, follow "Database Connection Pool Exhausted" section

# 5. Force restart
docker stop medsync-api && sleep 5 && docker start medsync-api
# OR
systemctl restart medsync-api
```

### "500 Internal Server Error" on Specific Endpoint

```bash
# 1. Check if it's a hospital-scoping issue
# This endpoint may fail if user's hospital doesn't match resource's hospital

# 2. Check database for the resource
psql -U postgres -d medsync_db -c "SELECT * FROM patients_patient WHERE id='<patient_id>';"

# Verify hospital_id matches user's hospital_id

# 3. Check logs for specific error
docker logs medsync-api | grep "500\|ERROR" | tail -20

# 4. Reproduce issue locally (if safe)
curl -X GET http://localhost:8000/api/v1/endpoint \
  -H "Authorization: Bearer <token>" \
  -v

# 5. Check permissions - is user role allowed?
# See Role Matrix in API_REFERENCE.md
```

### "Database Connection Refused"

```bash
# 1. Check if Postgres is running
docker ps | grep postgres
# OR
systemctl status postgresql

# If not running:
docker start medsync-db
# OR
systemctl start postgresql

# 2. Check connection parameters
echo $DATABASE_URL
# Expected format: postgresql://user:password@localhost:5432/medsync_db

# 3. Test connection manually
psql -U postgres -h localhost -d medsync_db -c "SELECT 1"

# If auth fails, check password/user:
psql -U postgres -c "\l"  # List databases

# 4. If connection times out, check firewall
netstat -tulpn | grep 5432
# OR
telnet localhost 5432

# 5. If on cloud, check security groups / network ACLs
```

### "Redis Connection Error" / Cache Not Working

```bash
# 1. Check if Redis is running
docker ps | grep redis
# OR
systemctl status redis-server

# If not running:
docker start medsync-redis
# OR
systemctl start redis-server

# 2. Test Redis connectivity
redis-cli PING
# Expected: PONG

# 3. Check connection parameters
echo $REDIS_URL
# Expected: redis://localhost:6379/0

# 4. Check Redis memory usage
redis-cli INFO memory | grep used_memory_human

# If near max, clear cache:
redis-cli FLUSHDB

# 5. Check for Redis persistence issues
redis-cli BGSAVE  # Trigger background save

# 6. If still failing, restart
docker restart medsync-redis
```

### "Payment / Billing Integration Failed"

```bash
# 1. Check if payment service is online
curl -I https://payment-provider.com/health

# 2. Verify API credentials
echo $PAYMENT_API_KEY
# Should not be empty

# 3. Check recent payment attempts
psql -U postgres -d medsync_db -c "SELECT * FROM billing_invoice WHERE status='failed' ORDER BY created_at DESC LIMIT 10;"

# 4. Check logs for payment errors
grep -i "payment\|billing" /var/log/medsync/api.log | tail -20

# 5. Test payment endpoint
curl -X POST https://payment-provider.com/test \
  -H "Authorization: Bearer $PAYMENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"amount": 100, "currency": "GHS"}'

# 6. Re-retry failed payments
python manage.py retry_failed_payments --limit=10
```

### "Email Not Sending" / Users Not Receiving Invitations

```bash
# 1. Check if email service is configured
echo $EMAIL_HOST $EMAIL_PORT $EMAIL_USER
# All should be non-empty

# 2. Test email connectivity
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Body', 'from@medsync.gh', ['to@example.com'])

# Check for errors

# 3. Check email queue
psql -U postgres -d medsync_db -c "SELECT * FROM django_celery_results_taskresult WHERE task_name LIKE '%email%' ORDER BY date_done DESC LIMIT 10;"

# 4. Check Celery task status
celery -A medsync_backend inspect active | jq '.[] | select(.name | contains("email"))'

# 5. Check email logs (if available from provider)
# For Gmail: https://myaccount.google.com/security
# For SendGrid: https://app.sendgrid.com/email_activity

# 6. Restart email service
systemctl restart medsync-email-service
# OR if using Celery:
celery -A medsync_backend worker -l info -E
```

---

## Performance Tuning

### Database Query Optimization

1. **Enable slow query logging:**
   ```bash
   psql -U postgres -d medsync_db -c "ALTER SYSTEM SET log_min_duration_statement = 100;"
   # Logs all queries > 100ms
   
   # Then restart Postgres
   docker restart medsync-db
   
   # Check slow queries
   tail -100 /var/log/postgresql/postgresql.log | grep "duration:"
   ```

2. **Create indexes for common filters:**
   ```sql
   CREATE INDEX CONCURRENTLY idx_audit_timestamp ON audit_log(created_at DESC);
   CREATE INDEX CONCURRENTLY idx_patient_hospital_status ON patients_patient(hospital_id, account_status);
   CREATE INDEX CONCURRENTLY idx_encounter_patient_date ON records_encounter(patient_id, start_time DESC);
   ```

3. **Archive old data (if storage is issue):**
   ```bash
   # Archive audit logs older than 1 year
   python manage.py archive_old_audits --older_than_days=365
   
   # Archive patient records (soft delete)
   python manage.py soft_delete_inactive_patients --inactive_days=730
   ```

### Cache Optimization

```bash
# 1. Monitor cache hit rate
redis-cli INFO stats | grep keyspace_hits keyspace_misses

# Target: > 80% hit rate

# 2. Adjust cache TTL (Time To Live)
# In Django settings:
CACHES = {
    'default': {
        'TIMEOUT': 3600,  # 1 hour; reduce to 30 min if memory pressure
    }
}

# 3. Use cache warming (pre-populate cache on startup)
python manage.py warm_cache
# This pre-loads common queries: hospital list, departments, drug database, etc.

# 4. Implement cache invalidation on data changes
# Example:
@transaction.on_commit
def invalidate_patient_cache(patient_id):
    cache.delete(f'patient:{patient_id}')
    cache.delete('patient:list')
```

### AI Model Optimization

```bash
# 1. Monitor AI inference time
curl -s http://localhost:8000/api/v1/admin/ai/performance-metrics | jq '.inference_times | add / length'
# Expected: 500-1500ms for comprehensive analysis

# 2. Reduce batch size if memory pressure
INFERENCE_BATCH_SIZE = 4  # Default 8; reduce if OOM errors

# 3. Use model quantization (if available)
# 8-bit quantization can reduce memory by 75%

# 4. Pre-load model at startup
python manage.py shell
>>> from api.ml import load_model
>>> load_model()  # Warm up model, gets GPU ready

# 5. Monitor model cache
redis-cli --scan --pattern "model_cache:*" | wc -l
# If > 1000 entries, may need to clear
```

---

## On-Call Procedures

### Shift Handover Checklist (to next on-call engineer)

```
📋 Daily Runbook Handover

Time: _______  Date: _______
Outgoing Engineer: _________________
Incoming Engineer: _________________

✓ System Status
  - API Health: [ ] Healthy [ ] Degraded [ ] Down
  - Database: [ ] OK [ ] Warnings [ ] Issues
  - AI Model: [ ] Enabled [ ] Disabled [ ] Issues
  - Redis/Cache: [ ] OK [ ] Issues

✓ Active Incidents
  - Any ongoing issues? [ ] YES [ ] NO
  - If yes, describe: ___________________________________
  - Resolution steps taken: ___________________________________
  - Next steps: ___________________________________

✓ Recent Deployments
  - Any recent code changes? [ ] YES [ ] NO
  - What was deployed: ___________________________________
  - Any issues observed: [ ] NO [ ] YES: _______________

✓ Upcoming Maintenance
  - Scheduled maintenance today? [ ] YES [ ] NO
  - Time window: ___________________________________
  - What's being done: ___________________________________

✓ Critical Alerts to Watch
  - [ ] Database query latency > 500ms
  - [ ] Error rate > 1%
  - [ ] API response time > 5s
  - [ ] Memory usage > 85%
  - [ ] Failed background jobs > 10

✓ Contact Info Verification
  - Manager: _________________________ Phone: __________
  - Escalation 2: _________________ Phone: __________
  - Database admin: ________________ Phone: __________

✓ Incoming Engineer Acknowledgment
  - I have reviewed this handover: _____ (signature)
  - I am ready to take over on-call: _____ (signature)
  - Start time: _________ End time: _________
```

### Emergency Response Protocol

**IF SYSTEM IS DOWN / SEVERE INCIDENT:**

```
⚠️ EMERGENCY PROCEDURE

1. IMMEDIATE (< 1 minute):
   ☐ Declare SEV-1 incident in Slack #incidents
   ☐ Take incident commander role
   ☐ Check `/api/v1/health` endpoint for status
   ☐ Start incident timeline log (document everything)

2. ASSESS (2-5 minutes):
   ☐ Is patient care affected? YES/NO
     └─ If YES: Page on-call manager immediately
   ☐ What's broken? (API / DB / Cache / AI)
   ☐ Estimated impact: # patients affected
   ☐ Estimated time to recovery: _____ minutes

3. COMMUNICATE (ongoing):
   ☐ Post every 5 min in #incidents Slack channel
   ☐ Template:
     "Status: IN PROGRESS | 
      Issue: [describe briefly] | 
      ETA: [time] | 
      Impact: [# users]"

4. RESPOND (varies):
   ☐ Try restart procedure (see Common Incidents)
   ☐ If not resolved in 5 min: call manager
   ☐ If not resolved in 10 min: escalate to CTO
   ☐ Consider: Should we rollback last deployment?

5. RESOLVE & POST-MORTEM:
   ☐ System back online: post "RESOLVED"
   ☐ Within 24 hours: post-mortem meeting
   ☐ Root cause analysis document
   ☐ Prevention measures for future
```

---

## Monitoring & Alerting

### Key Metrics to Monitor

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| API Response Time (p99) | < 200ms | 200-500ms | > 500ms |
| Database Query Latency (p95) | < 100ms | 100-300ms | > 300ms |
| Error Rate | < 0.1% | 0.1-1% | > 1% |
| CPU Usage | < 60% | 60-80% | > 80% |
| Memory Usage | < 70% | 70-85% | > 85% |
| Disk Space (free) | > 20% | 10-20% | < 10% |
| Redis Hit Rate | > 85% | 75-85% | < 75% |
| Queue Backlog (tasks) | < 20 | 20-50 | > 50 |
| Failed Auth Attempts (per min) | < 1 | 1-5 | > 5 |
| Break-Glass Access (per day) | < 3 | 3-10 | > 10 |

### Alerting Rules (Example Prometheus Config)

```yaml
groups:
  - name: medsync_api
    interval: 30s
    rules:
      # API Response Time
      - alert: APIHighLatency
        expr: histogram_quantile(0.99, rate(http_request_duration_seconds[5m])) > 0.5
        for: 5m
        annotations:
          summary: "API response time > 500ms"
          
      # Error Rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
        for: 2m
        annotations:
          summary: "Error rate > 1%"
          
      # Database Connection Pool
      - alert: DBConnectionPoolExhausted
        expr: db_connection_pool_usage > 0.9
        for: 1m
        annotations:
          summary: "Database connection pool 90% full"
          
      # Memory Leak Detection
      - alert: MemoryLeakSuspected
        expr: rate(process_resident_memory_bytes[1h]) > 10485760  # > 10MB/hour
        for: 30m
        annotations:
          summary: "Memory growing > 10MB/hour (possible leak)"
          
      # Background Job Queue
      - alert: CeleryQueueBacklog
        expr: celery_queue_length > 50
        for: 5m
        annotations:
          summary: "Background job queue has > 50 pending tasks"
```

### Dashboard Essentials

Create dashboards for:

1. **System Overview** (visible to all staff):
   - API health status (green/red)
   - Current user count online
   - Active appointments today
   - Critical alerts count

2. **Operations Dashboard** (for on-call):
   - API response time trend (5m, 1h, 24h)
   - Error rate
   - Database query latency
   - CPU, memory, disk usage
   - Background job queue status
   - Recent incidents list

3. **Clinical Features** (for doctors):
   - AI model status
   - AI analysis job queue
   - Recent AI recommendations
   - Break-glass access log

---

## Contact & Escalation

### Support Contacts

| Role | Name | Phone | Slack | Email |
|------|------|-------|-------|-------|
| On-Call Engineer | [Rotation] | +233-50-XXX-XXXX | @on-call | on-call@medsync.gh |
| Operations Manager | [Name] | +233-50-XXX-XXXX | @ops-manager | ops@medsync.gh |
| Engineering Lead | [Name] | +233-50-XXX-XXXX | @eng-lead | lead@medsync.gh |
| CTO | [Name] | +233-50-XXX-XXXX | @cto | cto@medsync.gh |
| Database Admin | [Name] | +233-50-XXX-XXXX | @dba | dba@medsync.gh |

### Escalation Path

```
Issue Detected (alert or user report)
  ↓
Level 1: On-call Engineer (5 min SLA)
  ├─ Try basic troubleshooting
  ├─ Check "Common Incidents" section
  ├─ If resolved: document and close
  └─ If not resolved within 5 min: escalate
  
  ↓ (after 5 min unresolved)
Level 2: Engineering Manager (10 min SLA)
  ├─ Mobilize additional engineers
  ├─ May require rollback or hotfix
  ├─ Communication to executives
  └─ If resolved: RCA required
  
  ↓ (after 10 min unresolved, or if patient care affected)
Level 3: CTO & Executive Team (immediate)
  ├─ Declare public incident (if necessary)
  ├─ Activate disaster recovery if needed
  ├─ Legal/compliance notification (if data breach)
  └─ Post-incident review with board
```

### Incident Communication Template

```
📌 INCIDENT ALERT

🔴 Severity: [CRITICAL / HIGH / MEDIUM / LOW]
⏰ Start Time: [time]
📝 Issue: [Brief description of what's broken]
👥 Impact: [# patients affected] | [# hospitals affected]
📊 Status: [Investigating / In Progress / Resolved]
✅ ETA to Resolution: [time estimate]

For Updates: #incidents Slack channel
Questions: @on-call or call +233-50-XXX-XXXX

🔧 Technical Details (for engineers):
- Error: [main error message]
- Component: [API / DB / AI / Cache]
- Affected endpoints: [list]
- Action: [Restart / Rollback / Fix in progress]

---

UPDATE #1 (10:35 AM):
[Progress update]

UPDATE #2 (10:45 AM):
[Further progress or resolution]

✅ RESOLVED (10:52 AM):
[Resolution summary]
Post-mortem scheduled: [time]
```

---

## Quick Reference Commands

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Restart API
docker restart medsync-api
systemctl restart medsync-api

# Restart Database
docker restart medsync-db
systemctl restart postgresql

# Restart Redis
docker restart medsync-redis
systemctl restart redis-server

# Check logs (last 100 lines)
docker logs medsync-api | tail -100
journalctl -u medsync-api -n 100

# Follow logs in real-time
docker logs -f medsync-api
journalctl -u medsync-api -f

# Database connection test
psql -U postgres -h localhost -d medsync_db -c "SELECT 1"

# Redis connection test
redis-cli PING

# Clear cache (CAREFUL!)
redis-cli FLUSHDB

# Vacuum database (cleanup)
psql -U postgres -d medsync_db -c "VACUUM ANALYZE"

# Kill background job
celery -A medsync_backend revoke <task_id> --terminate

# View system resources
htop
docker stats

# Check disk space
df -h

# Archive old logs
gzip /var/log/medsync/api.log.* 
tar -czf medsync-logs-$(date +%Y%m%d).tar.gz /var/log/medsync/

# Enable verbose logging
export DJANGO_SETTINGS_MODULE=medsync_backend.settings.production
python manage.py shell -c "import logging; logging.basicConfig(level=logging.DEBUG)"

# Run Django management command
python manage.py <command> [options]

# Examples:
python manage.py migrate
python manage.py collectstatic
python manage.py cleanup_expired_tokens
python manage.py rebuild_faiss_index
```

---

**Last Updated:** 2025  
**Maintained by:** MedSync Operations Team  
**Questions?** Contact: ops@medsync.gh or #ops-support on Slack
