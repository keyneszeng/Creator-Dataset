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
