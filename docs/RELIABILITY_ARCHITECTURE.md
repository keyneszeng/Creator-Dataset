# Reliability Architecture

## Objective

Creator Dataset is expected to process Creators with hundreds or thousands of Posts over long periods. Reliability therefore takes priority over single-run speed.

The production execution model is:

```text
API
  ↓ enqueue
Durable Job Store
  ↓ claim with lease
Workers
  ↓
Idempotent Post stages
  ↓
Checkpoints / Media states / OCR / STT
  ↓
Parent Job reconciliation
```

## 1. Durable Queue

SQLite is currently both the metadata database and the V0.x durable queue.

Each Job supports:

- parent_job_id
- idempotency_key
- payload_json
- priority
- attempt / max_attempts
- next_retry_at
- lease_owner
- lease_expires_at
- heartbeat_at
- terminal timestamps

Runnable jobs are claimed inside an immediate transaction so two local workers cannot claim the same Job.

## 2. Worker Lease

A worker never owns a Job forever.

```text
claim
 ↓
RUNNING + lease_expires_at
 ↓
periodic heartbeat
 ↓
lease extended
```

If a Worker crashes:

```text
lease expires
 ↓
recover_expired_leases()
 ↓
RETRY
```

If max attempts are exhausted:

```text
FAILED
```

This is essential for machine reboot, process crash and forced deployment recovery.

## 3. Idempotency

Every stage must tolerate replay.

Current replay-safe state:

- Creator/Post use UPSERT
- Comments use platform comment_id uniqueness
- media source registration is unique
- Post detail can skip already persisted detail
- comment cursors are checkpointed
- reply threads have independent checkpoints
- media COMPLETE files are skipped
- OCR/STT successful outputs are skipped
- export files are regenerated deterministically
- API can accept an explicit idempotency key for enqueue requests

Retries therefore resume rather than restart the entire Creator.

## 4. Retry Policy

Retryable failures use exponential backoff with jitter.

Examples:

- network timeout
- transient platform/API failure
- incomplete pagination caused by bounded runs
- temporary media failure

Non-retryable / operator-required:

- missing integration
- invalid Post
- authentication required
- platform challenge / blocked session

Authentication/platform blocking is marked BLOCKED rather than aggressively retried.

## 5. Parent / Child Jobs

A Creator run is represented by a parent Job.

```text
CREATOR_PIPELINE
├── POST_PIPELINE A
├── POST_PIPELINE B
└── POST_PIPELINE C
```

The parent remains WAITING while children run.

When all children are terminal:

- all COMPLETE → parent COMPLETE
- any FAILED/PARTIAL/BLOCKED → parent PARTIAL

One bad Post does not discard successful Post datasets.

## 6. Shared Platform Rate Limit

Multiple Workers share a SQLite-backed minimum request interval.

This prevents independently running Workers from creating request bursts.

Current default is deliberately conservative and configurable through:

```text
CREATOR_DATASET_XHS_MIN_INTERVAL_SECONDS
```

Future adaptive control should additionally use observed 429/challenge rates.

## 7. SQLite Operating Envelope

SQLite is intentional for V0.x because it provides:

- zero-service local deployment
- transactional queue claims
- portable backups
- easy debugging

Current safeguards:

- WAL mode
- busy timeout
- short write transactions
- bounded workers
- shared rate limiting

Recommended V0.x operating envelope:

- one machine
- a small number of Workers
- local or attached SSD
- low-to-moderate concurrent writes

Do not put the SQLite database on an unreliable network filesystem.

## 8. Postgres Migration Boundary

Move to Postgres before:

- multi-host Workers
- sustained high concurrent writes
- multi-tenant SaaS
- HA/failover requirements
- very large Job history

The application already separates repositories/services from platform adapters, so the intended migration is:

```text
SQLite Repository implementation
            ↓
Postgres Repository implementation
```

API, PlatformAdapter and Dataset schema should remain stable.

A formal migration tool (Alembic or equivalent) should be introduced before the first production Postgres release.

## 9. Media Storage Migration

V0.x:

```text
local filesystem
```

Production:

```text
S3-compatible object storage
```

Database rows should continue storing logical object paths/checksums, not embedding large binary files.

SHA256 enables:

- integrity verification
- deduplication
- migration validation

## 10. Observability

System endpoint:

```http
GET /api/system/status
```

It reports:

- Job counts by status
- active Worker count
- Worker heartbeat/current job

Worker logs are JSON and carry fields such as:

- worker_id
- job_id
- creator_id
- post_id

Next production observability layer should add:

- Prometheus/OpenTelemetry metrics
- error-rate alerts
- queue-age alerts
- BLOCKED alerting
- disk-space monitoring

## 11. Dataset Versioning

Every Post export now includes:

```text
manifest.json
```

It records:

- dataset schema version
- pipeline API version
- generation timestamp
- file sizes
- SHA256 checksums

This allows datasets generated months apart to remain auditable after schema changes.

## 12. Backup Strategy

Minimum V0.x backup unit:

```text
database.sqlite3
+
data/
```

Backups should be snapshot-consistent.

For SQLite, use SQLite's backup mechanism or checkpoint WAL before filesystem snapshots rather than blindly copying an actively written database.

Exports are reproducible derived artifacts; raw/platform data, normalized DB rows and original media are the high-value source layer.

## 13. Next Reliability Milestones

Priority order:

1. durable queue + leases — implemented
2. worker heartbeat/observability — implemented
3. shared platform rate limit — implemented
4. versioned export manifest — implemented
5. raw API page snapshot store
6. explicit Repair Jobs
7. stage-level child Jobs instead of one POST_PIPELINE
8. schema migrations
9. object storage backend
10. Postgres backend
11. metrics/alerts
12. scheduled incremental Creator refresh
