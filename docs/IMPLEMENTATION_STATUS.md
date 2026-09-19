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

- [ ] post images download
- [ ] video download
- [ ] cover download
- [x] comment image URLs registered in media table
- [ ] media manifest
- [ ] SHA256
- [ ] retry

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
