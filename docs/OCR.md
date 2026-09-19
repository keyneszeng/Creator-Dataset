# OCR Pipeline

## Goal

All downloaded post images and comment images should be converted into searchable text before downstream analysis.

The image remains the source artifact. OCR text is a derived layer.

```text
Image
  ↓
Local media file
  ↓
OCR Engine
  ↓
Text blocks + confidence + coordinates
  ↓
ocr_results
  ↓
Knowledge / Search / Analysis
```

## Why OCR is stored separately

Do not overwrite the original Post or Comment text with OCR output.

Keeping OCR separate lets us:

- re-run OCR with a better model later
- compare multiple OCR engines
- preserve recognition confidence
- trace text back to a specific source image
- avoid mixing author text with text embedded in screenshots

## V0.1 Engine

Default local engine:

- RapidOCR
- ONNX Runtime
- Chinese + English default mode

Install:

```bash
pip install -e ".[dev,xhs,ocr]"
```

RapidOCR is behind the `OcrEngine` protocol. A future PaddleOCR provider can be added without changing storage or API contracts.

## Data Model

Each OCR run stores:

- media_id
- engine
- engine_version
- language
- full_text
- average_confidence
- blocks_json
- status
- error

A block contains:

```json
{
  "text": "识别出的文字",
  "confidence": 0.982,
  "box": [[10, 20], [200, 20], [200, 50], [10, 50]]
}
```

## Supported media

OCR candidates:

- post image
- cover
- comment image

Video OCR is intentionally separate. Future work can sample keyframes and run the same OCR pipeline.

## API

```http
POST /api/posts/{post_id}/ocr-images
```

Example:

```json
{
  "include_comment_images": true,
  "only_missing": true,
  "limit": 200
}
```

Response:

```json
{
  "processed": 83,
  "skipped": 12,
  "failed": 1,
  "total_candidates": 96
}
```

## Analysis rule

Downstream analysis should use both:

```text
source text
+
OCR text
```

but preserve provenance.

Recommended normalized analysis unit:

```json
{
  "source_type": "post_image",
  "post_id": "...",
  "comment_id": null,
  "media_id": 123,
  "text": "...",
  "confidence": 0.96,
  "provenance": "ocr"
}
```

This makes OCR-derived claims traceable back to the original image.
