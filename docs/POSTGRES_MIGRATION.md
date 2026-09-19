# PostgreSQL Migration

## Status

The PostgreSQL Durable Job repository is implemented, but global
`database_backend=postgres` is intentionally not enabled yet.

Reason: enabling only Jobs in PostgreSQL while Creator/Post/Comment/Media state
remains in host-local SQLite would create split-brain deployments.

## Implemented

```text
DurableJobRepository contract
├── SQLite JobRepository
└── PostgresJobRepository
```

The PostgreSQL implementation supports:

- enqueue + idempotency key
- Job dependencies
- atomic multi-worker claim
- `FOR UPDATE SKIP LOCKED`
- lease / heartbeat
- expired lease recovery
- retry scheduling
- parent/child reconciliation
- Job tree
- targeted repair
- queue summary

## Why SKIP LOCKED

Multiple Workers can execute:

```text
SELECT candidate
FOR UPDATE SKIP LOCKED
```

inside concurrent transactions.

Each Worker skips Jobs already locked by another Worker rather than blocking or
double-claiming them.

This is the key primitive required for multi-host Worker scaling.

## Migration Order

Do not migrate every repository in one large rewrite.

Recommended order:

1. Durable Jobs — implementation complete
2. Worker registry
3. rate-limit state
4. Creator / Post
5. Comments / Checkpoints / Crawl audits
6. Media metadata / OCR / STT / Text units
7. Scheduler / Refresh runs / Change events
8. Raw snapshots
9. Export metadata where required
10. switch application-wide backend flag

## Cutover Rule

Only enable:

```text
CREATOR_DATASET_DATABASE_BACKEND=postgres
```

after all state required by API, Worker and Scheduler is backed by PostgreSQL.

Before that point, SQLite remains the only selectable application database
backend even though the PostgreSQL Job implementation exists and is tested.

## Target Cloud Topology

```text
Load Balancer
      ↓
API replicas
      ↓
Postgres
      ↓
Worker replicas
      ↓
S3-compatible storage

Scheduler singleton / leader
```

## Contract Strategy

Services should depend on repository contracts rather than SQL dialects.

The first extracted contract is:

```text
DurableJobRepository
```

The same pattern will be applied to the remaining bounded domains.

## Testing

PostgreSQL work has two test layers:

1. unit/contract tests that run without PostgreSQL,
2. PostgreSQL integration tests in CI using a service container.

The integration test layer should be introduced before global Postgres cutover.
