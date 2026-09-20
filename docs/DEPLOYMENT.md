# Deployment Architecture

## Deployment Modes

Creator Dataset supports two explicit deployment profiles.

### 1. Local

```text
One machine
├── API
├── Worker
├── Scheduler
├── SQLite
└── Local Object Store
```

Use this for:

- personal research
- development
- creator knowledge-base prototyping
- offline/private datasets
- small teams on one host

Recommended startup:

```bash
docker compose -f deploy/local/docker-compose.yml up -d
```

or run processes directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
creator-dataset-worker
creator-dataset-scheduler
```

### 2. Cloud Single-node

```text
One cloud VM / Docker host
├── API
├── Worker
├── Scheduler
├── persistent SQLite state volume
└── S3-compatible Object Storage
```

This is the supported V0.x cloud topology.

Use:

```text
CREATOR_DATASET_DEPLOYMENT_MODE=cloud
CREATOR_DATASET_DATABASE_BACKEND=sqlite
CREATOR_DATASET_STORAGE_BACKEND=s3
```

Media can live in:

- AWS S3
- Cloudflare R2
- MinIO
- other S3-compatible services

### 3. Cloud Multi-node — Supported

Target topology:

```text
Load Balancer
      ↓
API replicas
      ↓
Postgres
      ↓
Distributed Workers
      ↓
S3/Object Storage

Scheduler singleton / leader
```

This topology is supported when:

```text
CREATOR_DATASET_DATABASE_BACKEND=postgres
CREATOR_DATASET_STORAGE_BACKEND=s3
```

PostgreSQL coordinates Worker claims and leases with row locking, while all Workers share S3-compatible object storage.

SQLite remains single-host only. Do not place SQLite on a network filesystem and run Workers across multiple hosts.

## Capability Introspection

```http
GET /api/system/capabilities
```

Current V0.x returns values such as:

```json
{
  "database_backend": "sqlite",
  "single_node_supported": true,
  "multi_host_workers_supported": false,
  "postgres_ready": false
}
```

This is intentionally explicit so deployment tooling cannot accidentally treat SQLite as a multi-host queue.

## Readiness

Shallow:

```http
GET /api/system/readiness
```

Deep database + object storage roundtrip:

```http
GET /api/system/readiness?deep_storage=true
```

Use shallow readiness frequently. Use deep storage readiness less often because it performs an actual storage write/read/delete cycle.

## Persistent Data

### Local

Persist:

```text
data/creator_dataset.sqlite3
data/objects/
```

### Cloud Single-node

Persist:

```text
/app/state/creator_dataset.sqlite3
```

Media lives in S3 and does not require a shared local media disk.

## Object Storage Model

Media rows contain:

- storage_backend
- storage_key
- local_path (legacy/local optimization)
- sha256

OCR/STT use the storage reference. For S3-backed media, Workers materialize the object to a temporary local file, process it, then remove the temporary file.

This permits future stateless Worker containers.

## Upgrade Model

Application startup:

```text
open database
↓
create latest tables when missing
↓
apply schema_migrations in order
↓
start API/Worker/Scheduler
```

Check schema:

```http
GET /api/system/readiness
```

The service is not considered ready when the recorded schema migration version differs from the application version.

## Secrets

Never commit:

- Xiaohongshu cookies
- S3 access keys
- cloud credentials

For local development use `.env`.

For cloud deployments prefer:

- AWS IAM roles / workload identity
- cloud secret managers
- container runtime secrets

## Cloud Migration Path

Recommended sequence:

### Phase A — Current

```text
SQLite + Local Storage
```

### Phase B — Supported now

```text
SQLite + S3
```

This decouples the large binary data first.

### Phase C — Next major infrastructure milestone

```text
Postgres + S3
```

Then enable:

- API replicas
- multi-host Workers
- HA database
- distributed durable queue claims

Decoupling object storage before database migration reduces migration risk.


## Personal Cloud Agent Service

For the current personal-use Agent product, use:

```text
deploy/cloud-personal/
```

This profile exposes one HTTPS origin:

```text
https://creator.example.com/mcp
https://creator.example.com/v1
https://creator.example.com/api
```

Consumers:

```text
ChatGPT / Codex / Agents → /mcp
Web / WeChat Mini Program → /v1
Admin / operations → /api
```

The current personal cloud security model uses one private Bearer token and explicit MCP Host allow-list.

See [../deploy/cloud-personal/README.md](../deploy/cloud-personal/README.md).
