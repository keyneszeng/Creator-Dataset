# Analysis Corpus

## Purpose

Creator Dataset keeps original source data and derived OCR data separate, but downstream analysis needs a simple text-oriented dataset.

The `text_units` layer is that bridge.

## Unit Types

Current unit types:

- `author_text`
- `image_ocr`
- `comment`
- `reply`
- `comment_image_ocr`

Each unit contains:

- source_key
- platform
- post_id
- comment_id
- media_id
- unit_type
- text
- confidence
- provenance

## Provenance

Platform-native text:

```text
provenance = platform_text
```

OCR-derived text:

```text
provenance = ocr
```

This distinction is important when analyzing claims, sentiment or factual content because OCR is probabilistic.

## Example

```json
{
  "source_key": "media:123:ocr:rapidocr",
  "platform": "xiaohongshu",
  "post_id": "note-1",
  "comment_id": null,
  "media_id": 123,
  "unit_type": "image_ocr",
  "text": "图片中识别出的正文",
  "confidence": 0.972,
  "provenance": "ocr"
}
```

## Materialization

The corpus is rebuilt from normalized post/comment/media/OCR data during export.

This makes `text_units` a derived index rather than the only copy of the text.

## Export

`POST /api/posts/{post_id}/export` produces:

- post.json
- comments.jsonl
- media.jsonl
- analysis.jsonl
- knowledge.md

For machine analysis, prefer `analysis.jsonl`.

For humans and simple LLM ingestion, `knowledge.md` is convenient.

## Future

Future unit types can include:

- `video_transcript`
- `video_frame_ocr`
- `audio_transcript`
- `quoted_text`
- `creator_reply` (semantic subtype)
- `table_extraction`

The core rule remains: every derived text unit must retain provenance.
