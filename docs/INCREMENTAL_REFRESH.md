# Incremental Refresh

## Goal

After the first full Creator import, future runs should process only new or materially changed content.

```text
CREATOR_REFRESH
└── CREATOR_DISCOVERY
    ↓
scan recent creator pages
    ↓
classify NEW / CHANGED / UNCHANGED
    ↓
refresh recent Post details
    ↓
classify changes by concern
    ↓
fan out only required Stage Jobs
```

## Change Classes

Post Detail changes are split into:

- content_changed
- media_changed
- engagement_changed
- comments_changed

This prevents engagement drift from triggering expensive OCR/STT work.

## Routing

### New Post

Runs:

```text
Comments
Media Download
OCR
STT
Validation
Export
```

The detail was already fetched during refresh.

### Content / Media Change

If media changed:

```text
Media Download
OCR
STT
Validation
Export
```

Comments are included only when the platform-reported comment count also changed.

### Comments Change Only

```text
Comments
Validation
Export
```

### Engagement Change Only

```text
Validation
Export
```

No media reprocessing is required.

## Early Stop

Creator feeds are typically newest-first. Incremental discovery therefore supports stopping after a configurable number of consecutive unchanged pages.

Default:

```text
max_pages = 3
stop_after_unchanged_pages = 2
max_recent_posts = 30
```

This is a cost-control heuristic, not a completeness proof. Periodic deeper reconciliation runs should still be scheduled.

## Durable API

```http
POST /api/creators/{creator_id}/enqueue-refresh
```

Example:

```json
{
  "max_pages": 3,
  "max_recent_posts": 30,
  "stop_after_unchanged_pages": 2,
  "idempotency_key": "creator-2026-09-19-refresh"
}
```

The API creates a WAITING `CREATOR_REFRESH` parent and a runnable `CREATOR_DISCOVERY` child.

## Audit Trail

Refreshes are recorded in:

- refresh_runs
- change_events
- raw_snapshots

This allows future analysis of when a Creator/Post changed and why downstream work was scheduled.

## Long-term Policy

Recommended cadence:

- frequent shallow incremental refresh
- occasional deeper reconciliation scan
- explicit repair runs for BLOCKED/PARTIAL stages

The scheduler itself is intentionally separate from the refresh execution logic.
