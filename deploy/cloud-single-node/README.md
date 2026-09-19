# Single-node Cloud Deployment

This profile is the supported cloud topology for the current SQLite-based V0.x release.

## Topology

```text
One cloud VM / one Docker host
├── API
├── Worker
├── Scheduler
├── SQLite state volume
└── S3-compatible object storage
```

Media is stored in S3-compatible object storage, so the persistent VM volume only needs database/state capacity.

## Important Boundary

Do **not** run API/Workers on multiple hosts against the same SQLite database.

Multi-host cloud execution is intentionally blocked at the architecture level until the Postgres repository backend is implemented.

## Required Configuration

Set at least:

```text
CREATOR_DATASET_DEPLOYMENT_MODE=cloud
CREATOR_DATASET_DATABASE_BACKEND=sqlite
CREATOR_DATASET_STORAGE_BACKEND=s3
CREATOR_DATASET_S3_BUCKET=...
CREATOR_DATASET_S3_REGION=...
```

For AWS S3, endpoint URL can remain empty.

For S3-compatible providers, set:

```text
CREATOR_DATASET_S3_ENDPOINT_URL=https://...
```

Credentials should be delivered through the cloud secret manager or workload identity where possible, rather than committed to files.

## Verify

After startup:

```text
GET /api/health
GET /api/system/capabilities
GET /api/system/status
```

The capability endpoint should report:

```json
{
  "deployment_mode": "cloud",
  "database_backend": "sqlite",
  "storage_backend": "s3",
  "single_node_supported": true,
  "multi_host_workers_supported": false
}
```
