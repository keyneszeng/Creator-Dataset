# Implementation Status

## Completed

### Foundation

- [x] Python 3.12 project
- [x] FastAPI
- [x] SQLite initialization
- [x] core tables
- [x] PlatformAdapter protocol
- [x] JobStatus / JobType
- [x] GitHub Actions CI
- [x] basic tests

### Xiaohongshu Milestone 1

- [x] Creator URL resolver
- [x] canonical URL normalization
- [x] environment credential boundary
- [x] Cookie parser
- [x] optional xiaohongshu-cli gateway
- [x] Creator profile fetch boundary
- [x] Creator normalization
- [x] Creator UPSERT

### Xiaohongshu Milestone 2

- [x] Creator posts page fetch boundary
- [x] defensive post page normalization
- [x] post discovery UPSERT
- [x] pagination cursor checkpoint
- [x] discovery resume semantics
- [x] configurable max_pages safety bound
- [x] POST /api/creators/import

## Current Runtime Flow

```text
POST /api/creators/import
        │
        ▼
resolve creator URL
        │
        ▼
load operator Cookie
        │
        ▼
fetch creator profile
        │
        ▼
UPSERT creator
        │
        ▼
load discovery checkpoint
        │
        ▼
fetch posts page(s)
        │
        ├── UPSERT posts
        └── save cursor
        │
        ▼
update discovered_post_count
```

## Next

### Milestone 3 — Post Detail

- [x] fetch post detail
- [x] preserve xsec context for discovered notes
- [x] normalize title/content/published_at
- [x] metrics
- [x] reported_comment_count
- [x] detail raw response persistence
- [x] batch enrichment API

Endpoint:

```text
POST /api/creators/{creator_id}/enrich-posts
```

### Milestone 4 — Media

- [x] post image URLs extracted from detail
- [x] video URLs extracted from detail
- [x] cover URLs extracted from detail
- [x] comment image URLs registered in media table
- [x] streamed media download
- [x] atomic file write
- [x] SHA256
- [x] retry FAILED media on later runs
- [x] SSRF-oriented URL validation
- [x] automatic download → OCR pipeline
- [x] OCR-aware post export
- [x] creator-level bulk media orchestration

### OCR

- [x] pluggable OcrEngine protocol
- [x] RapidOCR local provider
- [x] Chinese/English OCR mode
- [x] line text + confidence + bounding boxes
- [x] ocr_results persistence
- [x] OCR failure state
- [x] post image OCR API
- [x] comment image OCR support after media download

Endpoint:

```text
POST /api/posts/{post_id}/ocr-images
```

### Milestone 5/6 — Comments

- [x] root comment cursor pagination
- [x] sub-comment cursor pagination
- [x] root_comment_id
- [x] parent_comment_id
- [ ] comment media
- [x] per-thread checkpoint
- [x] thread completion tracking
- [x] resumable root pagination
- [x] resumable reply pagination

Endpoint:

```text
POST /api/posts/{post_id}/crawl-comments
```

### Milestone 8 — Audit

- [x] reported vs fetched
- [x] failed thread count
- [x] completeness ratio
- [x] COMPLETE / PARTIAL decision
- [x] pagination completion state


## Comment Crawling Documentation

See [COMMENT_CRAWLING.md](COMMENT_CRAWLING.md) for pagination, checkpoints and audit semantics.


## Media / OCR / Export Runtime Flow

```text
Post Detail
   ↓
register media
   ↓
POST /api/posts/{post_id}/process-media
   ↓
download + SHA256
   ↓
OCR images
   ↓
POST /api/posts/{post_id}/export
   ↓
post.json
comments.jsonl
media.jsonl
knowledge.md
```

See [MEDIA_PIPELINE.md](MEDIA_PIPELINE.md) and [OCR.md](OCR.md).


## Analysis Corpus

- [x] provenance-aware text_units table
- [x] author text units
- [x] post image OCR units
- [x] comment text units
- [x] reply text units
- [x] comment image OCR units
- [x] analysis.jsonl export
- [x] source_key idempotency

Recommended machine-analysis source:

```text
analysis.jsonl
```

See [ANALYSIS_CORPUS.md](ANALYSIS_CORPUS.md).


## STT

- [x] pluggable SttEngine protocol
- [x] faster-whisper provider
- [x] CPU INT8 default
- [x] timestamped transcript segments
- [x] language detection
- [x] transcripts persistence
- [x] standalone transcription API
- [x] automatic media pipeline integration
- [x] video_transcript analysis units
- [x] transcript-aware Markdown export

Endpoints:

```text
POST /api/posts/{post_id}/transcribe-videos
POST /api/posts/{post_id}/process-media
```

See [STT.md](STT.md).

## Creator Pipeline

- [x] persistent creator pipeline Job
- [x] per-Post child Jobs
- [x] bounded max_posts execution
- [x] Post Detail enrichment
- [x] Comments
- [x] Media download
- [x] OCR
- [x] STT
- [x] Export
- [x] PARTIAL status when individual Posts fail

Endpoint:

```text
POST /api/creators/{creator_id}/run-pipeline
```


## Long-running Reliability

- [x] SQLite WAL
- [x] busy timeout
- [x] durable PENDING/RETRY queue
- [x] atomic Worker claim
- [x] Worker lease
- [x] heartbeat
- [x] expired lease recovery
- [x] exponential backoff + jitter
- [x] max attempts
- [x] parent/child Jobs
- [x] explicit WAITING parent state
- [x] idempotency keys
- [x] repeated Creator runs
- [x] queue/Worker observability
- [x] JSON structured logs
- [x] shared cross-Worker platform request pacing
- [x] raw API response snapshots
- [x] dataset schema version metadata
- [x] export manifest + SHA256 checksums

Production-default endpoint:

```text
POST /api/creators/{creator_id}/enqueue-pipeline
```

Worker:

```bash
creator-dataset-worker
```

Monitoring:

```text
GET /api/system/status
GET /api/jobs/{job_id}/progress
```

See [RELIABILITY_ARCHITECTURE.md](RELIABILITY_ARCHITECTURE.md).


## Stage-level Jobs

- [x] job_dependencies DAG
- [x] POST_DETAIL stage
- [x] COMMENTS stage
- [x] MEDIA_DOWNLOAD stage
- [x] OCR stage
- [x] STT stage
- [x] VALIDATION gate
- [x] EXPORT stage
- [x] dependency-aware claiming
- [x] failed dependency propagation
- [x] nested Creator → Post → Stage parents
- [x] ancestor reconciliation
- [x] Job tree API
- [x] targeted repair subgraph
- [x] repair reopens ancestors to WAITING

Endpoints:

```text
GET  /api/jobs/{job_id}/tree
POST /api/jobs/{job_id}/repair
```

See [STAGE_JOBS.md](STAGE_JOBS.md).


## Incremental Refresh & Scheduling

- [x] CREATOR_REFRESH durable parent Job
- [x] CREATOR_DISCOVERY refresh child Job
- [x] shallow newest-first refresh scan
- [x] consecutive unchanged page early-stop
- [x] discovery fingerprints
- [x] content fingerprints
- [x] media fingerprints
- [x] engagement fingerprints
- [x] comment-count fingerprints
- [x] refresh_runs audit trail
- [x] change_events audit trail
- [x] selective Stage fan-out
- [x] comment checkpoint invalidation
- [x] active media reconciliation
- [x] persistent refresh schedules
- [x] dedicated Scheduler process
- [x] schedule idempotency
- [x] schedule pause/resume API
- [x] refresh history API
- [x] change events API
- [x] scheduler status in /api/system/status

Production processes:

```bash
uvicorn app.main:app
creator-dataset-worker
creator-dataset-scheduler
```

See:

- [INCREMENTAL_REFRESH.md](INCREMENTAL_REFRESH.md)
- [SCHEDULER.md](SCHEDULER.md)


## Deployment & Storage

- [x] explicit local/cloud deployment profiles
- [x] explicit SQLite single-node boundary
- [x] local object storage abstraction
- [x] S3-compatible object storage backend
- [x] media storage_backend/storage_key
- [x] legacy local_path compatibility
- [x] cloud media materialization for OCR
- [x] cloud media materialization for STT
- [x] local Docker image
- [x] local Docker Compose
- [x] single-node cloud Compose
- [x] deployment capability endpoint
- [x] database/object-storage readiness probe
- [x] deep storage roundtrip readiness
- [x] versioned schema_migrations
- [x] SQLite online backup CLI
- [x] backup/restore documentation
- [ ] Postgres repository backend
- [ ] multi-host durable workers
- [ ] Kubernetes/managed-container deployment profile

Supported today:

```text
Local             = SQLite + Local Storage
Cloud single-node = SQLite + S3
```

Not yet supported:

```text
Multi-host cloud = Postgres + S3
```

See [DEPLOYMENT.md](DEPLOYMENT.md) and [BACKUP_RESTORE.md](BACKUP_RESTORE.md).


## PostgreSQL / Multi-node Cloud

- [x] PostgreSQL Creator repository
- [x] PostgreSQL Post repository
- [x] PostgreSQL Comment repository
- [x] PostgreSQL Media repository
- [x] PostgreSQL OCR/STT repositories
- [x] PostgreSQL Refresh repositories
- [x] PostgreSQL Validation repository
- [x] PostgreSQL Worker registry
- [x] PostgreSQL shared platform rate limiter
- [x] Durable queue using FOR UPDATE SKIP LOCKED
- [x] concurrent Worker claim integration tests
- [x] concurrent idempotent enqueue test
- [x] Scheduler advisory leadership lock
- [x] Scheduler HA integration test
- [x] backend-factory operations APIs
- [x] versioned PostgreSQL migrations
- [x] migration advisory lock for rolling deploys
- [x] shared per-process PostgreSQL connection pool
- [x] graceful API pool shutdown
- [x] PostgreSQL pg_dump backup support
- [x] cloud-postgres Compose
- [x] Postgres + MinIO cloud-dev Compose
- [x] multi-host capability requires PostgreSQL + S3
- [x] API key authentication
- [x] Admin/member role isolation
- [ ] Prometheus / OpenTelemetry metrics
- [ ] queue-age / error-rate / storage alerts
- [ ] managed Kubernetes/ECS/Cloud Run templates
- [ ] automated restore drill


## SaaS Access & Billing

- [x] users table
- [x] Admin / Member roles
- [x] active / suspended account status
- [x] high-entropy API keys
- [x] API key hash-only persistence
- [x] bootstrap Admin flow
- [x] Admin-only internal operational APIs in SaaS mode
- [x] default 5 free Dataset credits
- [x] free / paid credit buckets
- [x] append-only credit ledger
- [x] permanent per-Post Dataset entitlements
- [x] duplicate unlock protection
- [x] concurrent Postgres unlock overspend protection
- [x] shared idempotent Dataset Generation Jobs
- [x] shared dataset_artifacts registry
- [x] authenticated local artifact download
- [x] short-lived S3 presigned artifact URLs
- [x] Admin user listing
- [x] role/status management
- [x] API key rotation/revocation
- [x] credit ledger inspection
- [x] creator submission ownership audit
- [x] provider-neutral BillingProvider boundary
- [x] idempotent billing_events
- [x] payment event → paid credit ledger transaction
- [x] SQLite SaaS backend
- [x] PostgreSQL SaaS backend
- [ ] self-service signup/login UI
- [ ] Stripe/Paddle provider adapter
- [ ] webhook signature verification adapter
- [ ] organization/team tenancy
- [ ] subscription plans / recurring credit grants

Member endpoints live under:

```text
/api/saas/*
```

See [SAAS.md](SAAS.md) and [BILLING.md](BILLING.md).
