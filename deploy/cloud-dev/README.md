# Cloud Development Stack

This stack runs the cloud architecture locally:

- PostgreSQL 16
- MinIO (S3-compatible object storage)
- API
- Worker
- Scheduler

It is useful before deploying to AWS, GCP, Azure, Fly.io, Render, Railway or another container platform.

## Start

```bash
docker compose -f deploy/cloud-dev/docker-compose.yml up -d --build
```

## Endpoints

- API: http://localhost:8000
- MinIO S3: http://localhost:9000
- MinIO Console: http://localhost:9001
- PostgreSQL: localhost:5432

## Verify

```text
GET /api/system/capabilities
GET /api/system/readiness?deep_storage=true
GET /api/system/status
```

Expected deployment capability:

```text
database_backend = postgres
storage_backend = s3
multi_host_workers_supported = true
```

## Scale Workers Locally

```bash
docker compose \
  -f deploy/cloud-dev/docker-compose.yml \
  up -d --scale worker=4
```

The Workers use PostgreSQL `FOR UPDATE SKIP LOCKED` and S3-compatible media storage, which mirrors the cloud execution model.
