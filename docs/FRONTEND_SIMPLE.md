# Simplified Frontend

## Product Rule

The frontend should expose the product outcome, not the data-engineering machinery.

Users should not need to understand:

- cursor pagination
- OCR engines
- STT engines
- Raw JSON
- Job DAGs
- storage keys
- fingerprints
- retries
- checkpoints

Those belong to Admin / Advanced views.

## Member Navigation

Keep the primary navigation to four items:

```text
Creators
Datasets
AI Organize
Account
```

## Screen 1 — Creators

Primary action:

```text
[ Paste Creator URL ] [ Add ]
```

Creator card:

```text
Creator Name
137 posts
Last updated: today

[ View Posts ]
```

Do not show Job IDs by default.

Use simple status language:

```text
Importing...
Ready
Needs attention
```

## Screen 2 — Post Catalog

Each Post card should show only:

```text
Title
Published date
Likes / Comments
Dataset status

[ Unlock ]
```

If unlocked:

```text
[ View Dataset ]
```

Do not expose raw Dataset file lists on the main card.

## Screen 3 — Dataset

Default result is a simplified reading view:

```text
Title

Summary

Key Points
• ...
• ...

Topics
#...

Audience / Comment Insights
• ...

[ Organize with AI ]
[ Download ]
[ Advanced ]
```

Advanced opens:

- raw author text
- OCR text
- transcript
- comments
- original Dataset artifacts
- provenance

## Screen 4 — AI Organize

Keep it intentionally small:

```text
Use model: [ My GPT / My Qwen / My DeepSeek ]

Organize as:
(•) Simple Summary
( ) Knowledge Notes
( ) Comment Insights
( ) Custom

[ Run ]
```

The AI result uses the same Simplified Result Schema, so the UI does not change by provider.

## Screen 5 — Account

Show:

```text
Free credits: 3
Paid credits: 50

Connected LLMs
- My GPT
- My Qwen

Payment
- Buy credits
- Payment history
```

## Admin UI

Admin may have a separate advanced console:

```text
Users
Payments
Creators
Jobs
Workers
Schedules
Storage
LLM Providers
System
```

Do not mix these controls into the Member UI.

## API Response Principle

Member APIs should return concise product fields.

Example Dataset view:

```json
{
  "title": "Post title",
  "summary": "...",
  "key_points": ["...", "..."],
  "topics": ["sleep", "baby"],
  "comment_insights": ["..."],
  "ready": true
}
```

Raw files remain downloadable but should not be the default response shape.
