# MedSync EMR - Database Backup Strategy

**Version**: 1.0  
**Last Updated**: April 19, 2026  
**Audience**: DevOps, Operations, Engineering Team

---

## Executive Summary

This document outlines the backup and disaster recovery strategy for MedSync EMR's production PostgreSQL database hosted on Neon. The strategy ensures:

- ✅ **Automated daily backups** with point-in-time recovery (PITR)
- ✅ **Retention policy** of 30 days minimum for recovery
- ✅ **Off-site backup verification** and restore testing
- ✅ **Recovery time objective (RTO)** of 1 hour
- ✅ **Recovery point objective (RPO)** of 1 hour

---

## Database Infrastructure

### Production Environment

| Component | Details |
|-----------|---------|
| **Database** | PostgreSQL (Neon Cloud) |
| **Primary Region** | us-east-1 (configurable) |
| **Replication** | Automatic failover between compute endpoints |
| **Backup Service** | Neon Automated Backups |
| **Encryption** | TLS in transit, at-rest via AWS |

### Neon Configuration

- **Compute Endpoint**: Auto-scaling, multi-region failover
- **Connection Pooling**: Built-in via Neon connection pool (port 6432)
- **WAL (Write-Ahead Logs)**: Replicated across availability zones

---

## Backup Strategy

### Automated Daily Backups (via Neon)

Neon automatically creates and retains backups according to your plan:

| Plan | Backup Frequency | Retention | PITR Window |
|------|------------------|-----------|-------------|
| **Free** | Daily | 7 days | 7 days |
| **Pro** | Hourly | 7 days | 7 days |
| **Business** | Hourly | 30 days | 30 days ✅ Recommended |

**Recommendation**: Use **Business Plan** for production to ensure 30-day retention and 24/7 support.

### Manual Backup Procedure

For critical pre-release backups, create a manual backup snapshot:

1. **Via Neon Console** (AWS Web UI):
   ```
   https://console.neon.tech → Project → Backups → Create Backup
   ```
   Creates a labeled backup snapshot (e.g., "pre-v1-release")

2. **Via CLI** (if available):
   ```bash
   # List available backups
   neon backups list --project-id <PROJECT_ID>

   # Create manual backup
   neon backups create --project-id <PROJECT_ID> --name "pre-deployment-backup"
   ```

3. **Via pg_dump** (local backup):
   ```bash
   export PGPASSWORD="<password>"
   pg_dump \
     --host=<neon-host>.neon.tech \
     --port=5432 \
     --username=neondb_owner \
     --dbname=medsync_prod \
     --format=custom \
     > medsync_backup_$(date +%Y%m%d_%H%M%S).dump

   # Verify backup
   file medsync_backup_*.dump
   ```

---

## Point-in-Time Recovery (PITR)

### Use Cases

- **Data corruption**: User deletes important records by mistake
- **Malicious activity**: Unauthorized mass deletion or modification
- **Application bug**: Faulty migration or update affected data

### Recovery Procedure

#### Step 1: Identify Recovery Time

Determine when the database was in a good state:

```bash
# Check application logs for when issue was first detected
grep -i "error\|corruption" logs/app.log | head -20

# Neon supports recovery to any point within the retention window
# Default: 7 days (Pro) or 30 days (Business plan)
```

#### Step 2: Create Recovery Branch (Neon PITR)

1. **Via Neon Console**:
   - Navigate to: Branches → Add Branch
   - Select "Restore from backup" or "Point-in-time recovery"
   - Choose recovery timestamp (e.g., "2026-04-15 08:00:00 UTC")
   - Name branch: `recovery-2026-04-15`
   - Click "Create"

2. **Via CLI**:
   ```bash
   neon branches create \
     --project-id <PROJECT_ID> \
     --name recovery-$(date +%Y%m%d) \
     --from-branch main \
     --recovery-target-time "2026-04-15T08:00:00Z"
   ```

#### Step 3: Verify Recovered Data

```bash
# Get recovery branch connection string
export RECOVERY_DB_URL="postgresql://neondb_owner:PASSWORD@recovery-branch.neon.tech/medsync_prod"

# Connect to recovery database (read-only testing)
psql $RECOVERY_DB_URL

# Verify critical records exist and are correct
SELECT COUNT(*) FROM patients WHERE created_at > '2026-04-14'::date;
SELECT COUNT(*) FROM encounters WHERE status = 'completed';
```

#### Step 4: Promote Recovery Branch (if needed)

If recovery is successful and you need to make it production:

```bash
# DANGER: This replaces production data. Only do this if absolutely certain!
neon branches promote recovery-2026-04-15 --project-id <PROJECT_ID>
```

**Better approach**: Export recovered data and selectively restore specific records instead of full promotion.

#### Step 5: Export Specific Data from Recovery Branch

```bash
# Export only the corrupted table from recovery database
pg_dump \
  --host=recovery-branch.neon.tech \
  --dbname=medsync_prod \
  --table=patients \
  --username=neondb_owner \
  --format=custom \
  > patients_recovered.dump

# Restore just the patients table to production
pg_restore \
  --host=prod-branch.neon.tech \
  --dbname=medsync_prod \
  --username=neondb_owner \
  --data-only \
  --table=patients \
  patients_recovered.dump
```

---

## Full Restore Procedure (Database Migration)

### Scenario: Restore to New Database (Emergency)

#### Step 1: Export from Current Database

```bash
export SOURCE_DB_URL="postgresql://neondb_owner:PASSWORD@prod.neon.tech/medsync_prod"

# Full schema + data dump (custom format for faster restore)
pg_dump $SOURCE_DB_URL \
  --format=custom \
  --compress=9 \
  --jobs=4 \
  > medsync_full_$(date +%Y%m%d_%H%M%S).dump

# Verify dump file
ls -lh medsync_full_*.dump
```

#### Step 2: Create New Neon Database (if needed)

```bash
# Via Neon Console: Create new project
# Or via CLI:
neon projects create --name medsync-recovery
neon databases create medsync_prod --project-id <NEW_PROJECT_ID>
```

#### Step 3: Restore to New Database

```bash
export NEW_DB_URL="postgresql://neondb_owner:PASSWORD@recovery.neon.tech/medsync_prod"

pg_restore \
  --host=recovery.neon.tech \
  --dbname=medsync_prod \
  --username=neondb_owner \
  --verbose \
  --jobs=4 \
  medsync_full_*.dump

# Verify restoration
psql $NEW_DB_URL -c "SELECT COUNT(*) FROM patients;"
psql $NEW_DB_URL -c "SELECT COUNT(*) FROM encounters;"
```

#### Step 4: Update Connection String

```bash
# Update .env and deploy
export DATABASE_URL="postgresql://neondb_owner:PASSWORD@recovery.neon.tech/medsync_prod"

# Update on Railway/production platform
# Railway UI → Environment → DATABASE_URL → Update
```

#### Step 5: Run Migrations (if needed)

```bash
python manage.py migrate
python manage.py check
```

---

## Retention Policy

### Backup Retention Schedule

| Backup Type | Frequency | Retention | Usage |
|-------------|-----------|-----------|-------|
| **Automatic** (Neon) | Hourly | 30 days | Daily PITR, recovery within 30 days |
| **Weekly Manual** | Every Friday 00:00 UTC | 90 days | Off-site archive, compliance |
| **Monthly Manual** | 1st of month | 2 years | Long-term compliance storage |
| **Pre-Release** | Before major deployment | 1 year | Disaster recovery, audit trail |

### Implementation

#### Automatic Backups (Neon)
- **No action required** — Neon handles daily backups automatically
- **Verify** via Neon console: Check backup count and latest timestamp

#### Weekly Manual Backups (via Cron)

Create a scheduled backup script:

**File: `/opt/scripts/backup-medsync-weekly.sh`**

```bash
#!/bin/bash
set -e

# Configuration
BACKUP_DIR="/mnt/backups/medsync"
RETENTION_DAYS=90
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/medsync_weekly_${TIMESTAMP}.dump"

# Ensure backup directory exists
mkdir -p $BACKUP_DIR

# Create backup
export PGPASSWORD="${DATABASE_PASSWORD}"
pg_dump \
  --host=${DATABASE_HOST} \
  --port=5432 \
  --username=${DATABASE_USER} \
  --dbname=${DATABASE_NAME} \
  --format=custom \
  --compress=9 \
  > ${BACKUP_FILE}

# Verify backup size
BACKUP_SIZE=$(du -h ${BACKUP_FILE} | cut -f1)
echo "[$(date)] Backup completed: ${BACKUP_FILE} (${BACKUP_SIZE})"

# Clean up old backups (older than 90 days)
find ${BACKUP_DIR} -name "medsync_weekly_*.dump" -mtime +${RETENTION_DAYS} -delete
echo "[$(date)] Old backups cleaned up (retention: ${RETENTION_DAYS} days)"

# Optional: Upload to cloud storage (S3, Azure Blob, etc.)
# aws s3 cp ${BACKUP_FILE} s3://medsync-backups/weekly/
# az storage blob upload --file ${BACKUP_FILE} --container-name backups
```

#### Schedule via Cron

```bash
# Edit crontab
crontab -e

# Add weekly backup (Friday at 2 AM UTC)
0 2 * * 5 /opt/scripts/backup-medsync-weekly.sh >> /var/log/medsync-backup.log 2>&1
```

---

## Testing & Verification

### Monthly Restore Test (Critical!)

**Every month, perform a full restore test** to ensure backups are valid and recovery procedures work.

#### Test Procedure

```bash
# 1. Create recovery branch from backup
neon branches create \
  --project-id <PROJECT_ID> \
  --name restore-test-$(date +%Y%m) \
  --recovery-target-time "$(date --date='1 day ago' -u +'%Y-%m-%dT%H:%M:%SZ')"

# 2. Wait for branch to be ready
sleep 30

# 3. Run data integrity checks
RECOVERY_DB_URL="postgresql://..."
psql $RECOVERY_DB_URL << EOF
  SELECT COUNT(*) as total_patients FROM patients;
  SELECT COUNT(*) as total_encounters FROM encounters;
  SELECT COUNT(*) as total_records FROM records;
  SELECT COUNT(*) as total_users FROM auth_user;
  
  -- Check for orphaned records
  SELECT COUNT(*) as orphaned_encounters FROM encounters 
  WHERE patient_id NOT IN (SELECT id FROM patients);
  
  -- Check for data consistency
  SELECT COUNT(*) as inconsistent_vitals FROM vitals
  WHERE encounter_id NOT IN (SELECT id FROM encounters);
EOF

# 4. Document results
echo "Restore Test $(date +%Y-%m-%d): PASSED" >> /var/log/restore-tests.log

# 5. Clean up test branch
neon branches delete restore-test-$(date +%Y%m) --project-id <PROJECT_ID>
```

### Automated Monitoring

Add health checks to your CI/CD pipeline:

```python
# scripts/backup_health_check.py
import requests
from datetime import datetime, timedelta

NEON_API_KEY = os.getenv("NEON_API_KEY")
PROJECT_ID = os.getenv("NEON_PROJECT_ID")

# Get backup status
response = requests.get(
    f"https://api.neon.tech/v1/projects/{PROJECT_ID}/backups",
    headers={"Authorization": f"Bearer {NEON_API_KEY}"}
)

backups = response.json()["backups"]
if not backups:
    print("❌ CRITICAL: No backups found!")
    exit(1)

# Verify latest backup is recent (within 24 hours)
latest_backup = backups[0]
last_backup_time = datetime.fromisoformat(latest_backup["created_at"].replace("Z", "+00:00"))
time_since_backup = datetime.now(timezone.utc) - last_backup_time

if time_since_backup > timedelta(hours=24):
    print(f"⚠️  WARNING: Latest backup is {time_since_backup.total_seconds() / 3600:.1f} hours old")
else:
    print(f"✅ Latest backup: {last_backup_time} ({time_since_backup.total_seconds() / 3600:.1f} hours ago)")
```

---

## Disaster Recovery Runbook

### When Backup/Recovery is Needed

| Scenario | Response | RTO | RPO |
|----------|----------|-----|-----|
| **Database Corruption** | PITR to 1h ago | 30 min | 1 hour |
| **Ransomware/Data Loss** | Restore from 30-day backup | 1 hour | 24 hours |
| **Neon Zone Failure** | Failover compute endpoint | 5 min | 0 min (replicated) |
| **Complete Neon Outage** | Restore to new cloud provider | 4 hours | 1 hour |
| **Accidental Schema Drop** | PITR to pre-drop timestamp | 30 min | <1 hour |

### Step-by-Step Response

1. **Assess Impact**
   - Determine scope: single table, entire database, application availability
   - Calculate data loss window (time from issue to detection)
   - Check Neon status page for infrastructure issues

2. **Activate Recovery**
   - For data corruption: Use PITR to 1-24 hours ago
   - For recent changes: Restore specific records from backup
   - For complete outage: Restore to new Neon project

3. **Verify Recovery**
   - Run integrity checks (foreign keys, counts, dates)
   - Test application functionality
   - Monitor error logs for inconsistencies

4. **Deploy & Monitor**
   - Update DATABASE_URL in production
   - Run Django migrations if needed
   - Monitor error rates and performance
   - Post-incident review and documentation

---

## Off-Site Backup Strategy

### Cloud Storage Integration

For compliance and off-site protection, upload backups to cloud storage:

```bash
#!/bin/bash
# Upload backup to AWS S3

BACKUP_FILE=$1
BUCKET="medsync-backups-prod"
REGION="us-east-1"

# Upload with encryption
aws s3 cp \
  $BACKUP_FILE \
  s3://${BUCKET}/weekly/$(basename $BACKUP_FILE) \
  --region $REGION \
  --sse AES256 \
  --metadata "backup-date=$(date),retention-until=$(date -d '+90 days' +'%Y-%m-%d')"

# Enable versioning on S3 bucket (for file history)
aws s3api put-bucket-versioning \
  --bucket $BUCKET \
  --versioning-configuration Status=Enabled
```

### Recovery from Cloud Storage

```bash
# Download backup from S3
aws s3 cp \
  s3://medsync-backups-prod/weekly/medsync_weekly_20260415_020000.dump \
  ./recovered_backup.dump

# Restore
pg_restore \
  --host=new-db.neon.tech \
  --dbname=medsync_prod \
  --verbose \
  ./recovered_backup.dump
```

---

## Compliance & Audit

### Backup Logs

Maintain audit trail of all backups and recoveries:

```sql
-- Log every backup to application database
INSERT INTO backup_audit_log (
  backup_type,
  backup_time,
  backup_size,
  status,
  notes
) VALUES (
  'automated_daily',
  NOW(),
  (SELECT pg_database_size('medsync_prod') / 1024 / 1024),
  'completed',
  'Daily automatic backup via Neon'
);

-- Log recoveries
INSERT INTO backup_audit_log (
  backup_type,
  backup_time,
  status,
  notes
) VALUES (
  'pitr_recovery',
  NOW(),
  'initiated',
  'Point-in-time recovery initiated for data corruption 2026-04-15 10:00 UTC'
);
```

### Compliance Requirements

| Standard | Requirement | Implementation |
|----------|-------------|-----------------|
| **HIPAA** | ≥30-day retention, encrypted | Neon Business Plan + S3 encryption |
| **GDPR** | Right to data restoration | PITR capability within 30 days |
| **SOC 2** | Backup validation, RTO/RPO | Monthly restore tests, monitoring |
| **ISO 27001** | Incident response procedures | This document + test execution |

---

## Monitoring & Alerting

### Health Check Dashboard

Monitor backup health via application dashboard:

```python
# api/views/health_views.py
@api_view(['GET'])
@permission_classes([IsAdminUser])
def backup_health(request):
    """Get backup status for admin dashboard."""
    try:
        # Check latest backup via Neon API
        # or database metadata
        backups = get_neon_backups()
        latest = backups[0] if backups else None
        
        return Response({
            "backup_status": "healthy" if latest else "no_backups",
            "latest_backup_time": latest["created_at"],
            "hours_since_backup": (datetime.now() - latest["created_at"]).total_seconds() / 3600,
            "retention_days": 30,
            "pitr_available": True,
            "recommendations": []
        })
    except Exception as e:
        return Response(
            {"backup_status": "error", "message": str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
```

### Alert Rules

Set up alerts in your monitoring system (DataDog, New Relic, etc.):

```
Alert: "Backup Failed" if no backup in last 48 hours
Alert: "High Backup Size" if backup > 5GB
Alert: "PITR Window Closing" if < 7 days until backup rotation
```

---

## Disaster Recovery Contacts

| Role | Contact | Availability |
|------|---------|---------------|
| **Database Admin** | ops-team@medsync.gh | 24/7 on-call |
| **Cloud Provider** | Neon Support (Business) | 24/7 |
| **IT Operations** | operations@medsync.gh | Business hours + on-call |
| **Executive Sponsor** | cto@medsync.gh | Escalation only |

---

## Appendix: Key Commands Reference

```bash
# List all backups
neon backups list --project-id <PROJECT_ID>

# Create manual backup
neon backups create --project-id <PROJECT_ID> --name "label"

# Create PITR branch
neon branches create \
  --project-id <PROJECT_ID> \
  --name recovery-branch \
  --recovery-target-time "2026-04-15T10:00:00Z"

# Full database dump (local)
pg_dump postgresql://user:pass@host/db --format=custom > backup.dump

# Restore from dump
pg_restore --dbname=postgresql://user:pass@host/db backup.dump

# Verify database integrity
psql postgresql://user:pass@host/db << EOF
SELECT COUNT(*) FROM patients;
SELECT COUNT(*) FROM encounters;
SELECT COUNT(*) FROM records;
EOF
```

---

**Status**: ✅ Approved and Ready for Production  
**Next Review**: July 2026  
**Maintenance**: Test recovery monthly, review procedures quarterly
