# Media Pipeline

## Goal

Turn every discovered media URL into a locally archived, hash-addressable and analyzable artifact.

```text
Post Detail / Comment
        ↓
register media URL
        ↓
media.download_status=PENDING
        ↓
download
        ↓
atomic file write
        ↓
SHA256
        ↓
COMPLETE
        ↓
image? ── yes ──> OCR
        ↓
     export
```

## Media Sources

V0.1 supports registering:

- post images
- post cover
- post video
- comment images

Post media are extracted during Post Detail enrichment. Comment images are registered while comments are persisted.

## Download Safety

The downloader:

- only accepts HTTP/HTTPS
- rejects localhost
- resolves the hostname and rejects private/link-local/loopback/reserved addresses
- validates redirect destinations again
- limits individual media size (default 250 MB)
- streams instead of loading the whole file into memory
- writes to a temporary `.part` file
- atomically renames on success
- calculates SHA256 during streaming

This prevents the media fetcher from becoming an unrestricted internal-network fetch primitive.

## Storage

Example:

```text
data/
└── xiaohongshu/
    └── posts/
        └── <post_id>/
            ├── media/
            │   ├── 12_image.webp
            │   ├── 13_image.webp
            │   └── 14_video.mp4
            ├── comments/
            │   └── <comment_id>/
            │       └── 31_comment_image.jpg
            └── export/
```

## Automatic Processing API

```http
POST /api/posts/{post_id}/process-media
```

Body:

```json
{
  "download_limit": 200,
  "run_ocr": true,
  "ocr_limit": 500
}
```

This downloads pending/failed media and then OCRs downloaded image/cover/comment-image files that do not already have a successful OCR result.

## Retry Semantics

Media states:

- PENDING
- RUNNING
- COMPLETE
- FAILED

A later pipeline run automatically retries FAILED media.

## Export

```http
POST /api/posts/{post_id}/export
```

Produces:

- `post.json`
- `comments.jsonl`
- `media.jsonl`
- `knowledge.md`

The Markdown export includes:

- author text
- OCR from post images
- comment text
- OCR from comment images
- media IDs and confidence metadata

OCR text is never silently merged into author text; provenance is preserved.
