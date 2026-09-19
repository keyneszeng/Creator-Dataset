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

- [ ] fetch post detail
- [ ] preserve xsec context for discovered notes
- [ ] normalize title/content/published_at
- [ ] metrics
- [ ] reported_comment_count
- [ ] raw response archive

### Milestone 4 — Media

- [ ] images
- [ ] video
- [ ] cover
- [ ] media manifest
- [ ] SHA256
- [ ] retry

### Milestone 5/6 — Comments

- [ ] root comment cursor pagination
- [ ] sub-comment cursor pagination
- [ ] root_comment_id
- [ ] parent_comment_id
- [ ] comment media
- [ ] thread completion tracking

### Milestone 8 — Audit

- [ ] reported vs fetched
- [ ] failed thread count
- [ ] completeness ratio
- [ ] COMPLETE / PARTIAL decision
