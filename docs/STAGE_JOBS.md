# Stage Jobs

## Why Stage Jobs

A Post pipeline is too large to be a single retry unit.

The durable execution model is now:

```text
CREATOR_PIPELINE
└── POST_PIPELINE
    ├── POST_DETAIL
    ├── COMMENTS
    ├── MEDIA_DOWNLOAD
    ├── OCR
    ├── STT
    ├── VALIDATION
    └── EXPORT
```

Each Post is a WAITING parent Job. The executable work lives in its Stage Jobs.

## Dependency Graph

Default graph:

```text
POST_DETAIL
   ├──────────────► COMMENTS ──────────────┐
   │                                        │
   └──────────────► MEDIA_DOWNLOAD ──────┐  │
                         │                │  │
                         ├──► OCR ────────┤  │
                         └──► STT ────────┤  │
                                          ▼  ▼
                                       VALIDATION
                                           │
                                           ▼
                                         EXPORT
```

OCR and STT can run independently after media download.

The queue stores dependencies in `job_dependencies`. A Worker can only claim a Job when all required dependencies are COMPLETE.

## Failure Propagation

If a required dependency becomes:

- FAILED
- PARTIAL
- BLOCKED

dependent Jobs are marked PARTIAL rather than left permanently PENDING.

The Post parent then reconciles to PARTIAL, and the Creator parent becomes PARTIAL when all Posts reach terminal states.

## Targeted Repair

Operator endpoint:

```http
POST /api/jobs/{job_id}/repair
```

Repair reopens:

1. the selected Stage,
2. all downstream dependent Stages,
3. Post/Creator parents back to WAITING.

Example:

```text
MEDIA_DOWNLOAD failed
    ↓ repair
MEDIA_DOWNLOAD = PENDING
OCR = PENDING
STT = PENDING
VALIDATION = PENDING
EXPORT = PENDING
```

Completed independent stages such as COMMENTS are left untouched.

## Job Tree

Inspect the complete hierarchy:

```http
GET /api/jobs/{job_id}/tree
```

Each node exposes its dependency IDs so a UI can render the execution DAG.

## Validation Stage

VALIDATION is the gate before Export.

It currently checks configured requirements:

- Post Detail exists
- comments status is COMPLETE
- media have completed downloads
- downloaded images have successful OCR
- downloaded videos have successful STT

If validation fails, it is retryable. This makes "dataset ready" an explicit system decision rather than assuming earlier stage success means the final dataset is complete.

## Long-term Direction

The current coarse COMMENTS stage internally uses root/reply checkpoints.

A future refinement can fan out further:

```text
COMMENTS
├── ROOT_COMMENTS page jobs
└── SUB_COMMENTS thread jobs
```

That should be introduced only when very large comment sections justify the extra Job volume.
