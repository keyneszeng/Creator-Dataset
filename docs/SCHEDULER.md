# Refresh Scheduler

## Purpose

The Scheduler keeps Creator datasets fresh without coupling scheduling to API requests or Worker execution.

```text
refresh_schedules
      ↓
Scheduler
      ↓ enqueue
CREATOR_REFRESH
      ↓
Durable Queue
      ↓
Workers
```

The Scheduler never crawls a platform directly.

## Processes

Run API:

```bash
uvicorn app.main:app
```

Run one or more Workers:

```bash
creator-dataset-worker
```

Run Scheduler:

```bash
creator-dataset-scheduler
```

## Create / Update Schedule

```http
PUT /api/creators/{creator_id}/refresh-schedule
```

Example:

```json
{
  "interval_minutes": 1440,
  "max_pages": 3,
  "max_recent_posts": 30,
  "stop_after_unchanged_pages": 2,
  "run_immediately": true
}
```

Minimum interval is currently 60 minutes.

## Pause / Resume

```http
POST /api/refresh-schedules/{schedule_id}/pause
POST /api/refresh-schedules/{schedule_id}/resume
```

## Inspect

```http
GET /api/refresh-schedules
GET /api/creators/{creator_id}/refresh-history
GET /api/creators/{creator_id}/changes
GET /api/system/status
```

## Delivery Semantics

A due schedule gets a deterministic idempotency key derived from:

```text
schedule_id + scheduled next_run_at
```

If the Scheduler crashes after enqueue but before advancing the schedule, the next pass reuses the same key instead of creating a duplicate refresh.

After successful enqueue, `next_run_at` advances by the configured interval.

## Recommended Policy

For most Creators:

- shallow refresh every 24 hours
- more frequent refresh only for highly active Creators
- occasional deeper reconciliation
- targeted Repair for PARTIAL/BLOCKED stages

The scheduler cadence controls freshness; the Stage Job system controls cost.
