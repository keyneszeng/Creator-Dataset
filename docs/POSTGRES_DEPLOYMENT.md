# PostgreSQL Multi-node Deployment

## Purpose

PostgreSQL is the database backend for multi-host Creator Dataset deployments.

It replaces SQLite for:

- durable Job coordination
- Worker leases
- scheduler state
- creator/post/comment metadata
- refresh/change history
- cross-host rate limiting

Object media should remain in S3-compatible storage.

## Topology

```text
Load Balancer
   ↓
API replicas
   ↓
PostgreSQL
   ↓
Worker replicas
   ↓
S3-compatible Object Storage

Scheduler replicas
   ↓
PostgreSQL advisory leadership lock
```

## Configuration

```text
CREATOR_DATASET_DEPLOYMENT_MODE=cloud
CREATOR_DATASET_DATABASE_BACKEND=postgres
CREATOR_DATASET_DATABASE_URL=postgresql://...
CREATOR_DATASET_STORAGE_BACKEND=s3
CREATOR_DATASET_S3_BUCKET=...
```

## Queue Coordination

PostgreSQL Job claiming uses:

```sql
FOR UPDATE SKIP LOCKED
```

This allows multiple Workers on multiple hosts to claim different runnable Jobs without a central Redis queue.

Worker ownership remains lease-based:

```text
claim
→ lease_owner
→ lease_expires_at
→ heartbeat
→ recovery on expiration
```

## Scheduler HA

Multiple Scheduler instances may run.

Only one becomes active for each scheduling pass through a PostgreSQL session advisory lock. Other replicas act as standby instances.

Scheduled refresh enqueue remains idempotent using the schedule ID and scheduled timestamp.

## Schema Upgrades

PostgreSQL schema changes are versioned in:

```text
schema_migrations
```

Startup acquires a transaction-scoped advisory migration lock, applies pending migrations in order, records each version, then releases the lock on commit.

This supports rolling deployments where several API replicas may start concurrently.

## Backups

Unified command:

```bash
creator-dataset-backup --output backups
```

For PostgreSQL this runs:

```text
pg_dump --format=custom
```

The container image includes PostgreSQL client tools.

For managed PostgreSQL also enable provider-native:

- point-in-time recovery
- automated snapshots
- cross-region backup where required

The CLI backup is an application-level export, not a replacement for managed PITR.

## Restore

For a custom-format backup:

```bash
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --dbname "$CREATOR_DATASET_DATABASE_URL" \
  creator_dataset.dump
```

After restore:

```text
GET /api/system/readiness
GET /api/system/status
```

Then verify S3 access:

```text
GET /api/system/readiness?deep_storage=true
```

## Scaling Workers

The supplied Compose profile can scale Worker replicas:

```bash
docker compose \
  -f deploy/cloud-postgres/docker-compose.yml \
  up -d --scale worker=4
```

All Worker replicas coordinate through PostgreSQL and share object media through S3.

## Operational Limits

Before large-scale production, still add:

- connection pooling
- managed Postgres sizing
- query latency metrics
- connection saturation alerts
- queue-age alerts
- S3 lifecycle/retention policy
