# Video Speech-to-Text

## Goal

Convert spoken content in downloaded videos into structured, provenance-aware text for downstream analysis.

```text
Downloaded video
    ↓
STT Engine
    ↓
language detection
    ↓
timestamped segments
    ↓
transcripts
    ↓
video_transcript text unit
    ↓
analysis.jsonl / knowledge.md
```

## V0.1 Engine

Default provider:

- faster-whisper
- CPU
- INT8
- model: small
- VAD enabled

Install:

```bash
pip install -e ".[dev,xhs,ocr,stt]"
```

The provider is behind the `SttEngine` protocol and can be replaced without changing the database or export contracts.

## Transcript Storage

Each successful transcript stores:

- media_id
- engine
- engine_version
- model
- detected language
- language probability
- full_text
- timestamped segments

Example segment:

```json
{
  "start": 1.24,
  "end": 4.92,
  "text": "这是视频中的一句话",
  "average_logprob": -0.18
}
```

## APIs

Standalone:

```http
POST /api/posts/{post_id}/transcribe-videos
```

Body:

```json
{
  "only_missing": true,
  "limit": 20
}
```

Automatic media pipeline:

```http
POST /api/posts/{post_id}/process-media
```

Body:

```json
{
  "download_limit": 200,
  "run_ocr": true,
  "ocr_limit": 500,
  "run_stt": true,
  "stt_limit": 20
}
```

## Analysis Corpus

A successful video transcript creates a derived text unit:

```json
{
  "unit_type": "video_transcript",
  "media_id": 123,
  "text": "...",
  "confidence": 0.98,
  "provenance": "stt"
}
```

The `confidence` field currently uses detected-language probability. Segment-level decoding confidence remains in the transcript segment archive.

## Provenance Rule

Video transcript text must not be merged into author text in storage.

The system keeps:

- platform-native text
- OCR-derived text
- STT-derived text

as separate provenance classes.

## Performance Note

STT is intentionally optional because transcription is substantially more compute-intensive than metadata crawling or OCR. The model can be changed later for different speed/accuracy tradeoffs.
