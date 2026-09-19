# PostgreSQL Cloud Deployment

This profile uses PostgreSQL for shared application state and S3-compatible
object storage for media.

## Topology

```text
API
 │
 ├──────────────┐
 │              │
 ▼              ▼
PostgreSQL   S3-compatible storage
 ▲
 │
 ├── Worker(s)
 └── Scheduler
```

PostgreSQL enables multiple Worker processes or hosts to coordinate through
`FOR UPDATE SKIP LOCKED`, leases and shared rate-limit state.

## Required environment

At minimum configure S3 values in `.env`:

```text
CREATOR_DATASET_S3_BUCKET=...
CREATOR_DATASET_S3_REGION=...
CREATOR_DATASET_S3_ENDPOINT_URL=...
CREATOR_DATASET_S3_ACCESS_KEY_ID=...
CREATOR_DATASET_S3_SECRET_ACCESS_KEY=...
```

For AWS S3, endpoint URL can remain unset.

Set a strong PostgreSQL password:

```bash
export POSTGRES_PASSWORD='...'
```

Then:

```bash
docker compose -f deploy/cloud-postgres/docker-compose.yml up -d --build
```

## Managed cloud deployment

For production, prefer:

- managed PostgreSQL
- managed S3-compatible object storage
- API replicas behind a load balancer
- independently scalable Worker replicas
- one Scheduler replica

Replace the compose `postgres` URL with the managed database URL.

## Worker scaling

On one Docker host:

```bash
docker compose -f deploy/cloud-postgres/docker-compose.yml up -d --scale worker=4
```

Across hosts/orchestrators, every Worker must point at the same PostgreSQL and
object store.

## Verification

```text
GET /api/system/capabilities
GET /api/system/readiness
GET /api/system/status
```

Expected capability:

```json
{
  "database_backend": "postgres",
  "multi_host_workers_supported": true,
  "postgres_ready": true
}
```
