# Creator Pipeline

## Purpose

The Creator-level pipeline turns the per-Post capabilities into a bounded orchestration flow.

```text
Creator
  ↓
select up to max_posts
  ↓
enrich missing post details
  ↓
for each post
  ├── crawl comments + replies
  ├── download media
  ├── OCR images
  ├── transcribe videos
  └── export dataset
  ↓
Creator pipeline Job status
```

## Run

```http
POST /api/creators/{creator_id}/run-pipeline
```

Example:

```json
{
  "max_posts": 20,
  "run_comments": true,
  "run_media": true,
  "run_ocr": true,
  "run_stt": true,
  "export": true
}
```

The response includes a persistent `job_id`.

## Job Status

```http
GET /api/jobs/{job_id}
```

Job states:

- PENDING
- RUNNING
- COMPLETE
- PARTIAL
- BLOCKED
- FAILED

The Creator pipeline creates:

- one Creator-level `CREATOR_PIPELINE` job
- one `POST_PIPELINE` child-style record per selected Post

The current schema does not yet persist an explicit parent_job_id; correlation is through creator_id/post_id. Adding parent-child job IDs is a future queue-engine improvement.

## Failure Semantics

One failed Post does not abort the remaining Creator.

If any selected Post fails or becomes partial:

```text
Creator Job = PARTIAL
```

Successful Posts remain persisted and exported.

## Bounded Execution

`max_posts` is mandatory for operational safety. The API currently caps it at 500.

This synchronous orchestrator is an intermediate V0.1 implementation. For large Creators, the same service boundaries should later run behind a durable worker queue.
