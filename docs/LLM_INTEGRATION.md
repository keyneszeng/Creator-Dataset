# User-connected LLM Organization

## Product Position

LLM organization is optional.

The source of truth remains the Creator Dataset:

```text
Raw / normalized Dataset
        ↓
Analysis Corpus
        ↓
optional user-connected LLM
        ↓
Simplified Derived Result
```

The LLM never overwrites:

- Creator
- Post
- Comments
- Media
- OCR
- STT
- raw snapshots
- Dataset artifacts

It only produces a derived user-facing view.

## Why BYO LLM

A user may prefer:

- their own OpenAI-compatible provider
- a company LLM gateway
- a local/self-hosted model
- a regional provider
- a model selected for a specific language/domain

Creator Dataset should not force one model vendor.

## Simple UX

Connecting a model asks only for:

```text
Name
Model
Base URL
API Key
[confirm external processing]
```

The Member UI does not expose:

- encrypted credential data
- prompts
- tokenization
- retry internals
- Job DAG
- source chunk IDs

## Organization Tasks

V1 tasks:

```text
simplify
summarize
extract_knowledge
comment_insights
custom
```

All tasks return the same result shape.

## Simplified Result Schema

```json
{
  "title": "...",
  "summary": "...",
  "key_points": ["..."],
  "topics": ["..."],
  "useful_facts": ["..."],
  "audience_questions": ["..."],
  "comment_insights": ["..."],
  "action_items": ["..."],
  "caveats": ["..."],
  "language": "..."
}
```

The frontend renders this Schema directly.

## Default View Without LLM

A user never needs an LLM connection to read an unlocked Dataset.

```http
GET /api/saas/datasets/{post_id}/view
```

Without an AI result, the API returns a deterministic compact view based on source content and metrics.

When an LLM organization run completes, the same endpoint automatically surfaces the latest completed derived result.

Therefore the page layout stays unchanged.

## BYO Credential Security

LLM API keys are:

- never returned after connection creation,
- never written into Dataset artifacts,
- never written into prompts,
- never logged intentionally,
- encrypted at rest using AES-GCM.

Server configuration:

```text
CREATOR_DATASET_LLM_CREDENTIAL_ENCRYPTION_KEY
```

The encryption key is server-side and must live in a secret manager in production.

## Endpoint Security / SSRF

Cloud/SaaS deployments do not allow arbitrary LLM destination hosts.

Administrators configure:

```text
CREATOR_DATASET_LLM_ALLOWED_HOSTS
```

Only exact allow-listed hosts are accepted in cloud mode.

HTTPS is required in cloud mode.

Local deployments may opt into custom/self-hosted endpoints, including a local OpenAI-compatible server.

## External Processing Consent

Connecting an external model requires explicit acknowledgement that unlocked Dataset text can be sent to the selected provider.

The system sends normalized text only.

The first adapter sends:

- Post author text
- OCR-derived text
- STT-derived transcript text
- Comment / reply text

It does not send original image/video binaries through the LLM organization path.

## Durable Execution

```text
User clicks Organize
      ↓
llm_organization_runs
      ↓
LLM_ORGANIZE Job
      ↓
Worker
      ↓
decrypt key in memory
      ↓
build bounded normalized text input
      ↓
provider request
      ↓
validate Simplified Result Schema
      ↓
store derived result
```

The API request does not wait for the external model.

## Input Bound

Default:

```text
CREATOR_DATASET_LLM_MAX_INPUT_CHARS=120000
```

This is a safety/cost bound, not a semantic guarantee.

Future work can replace simple truncation with deterministic text-unit selection and chunk/reduce organization for very large Datasets.

## Current Adapter

V1 includes an OpenAI-compatible adapter.

This is a protocol compatibility boundary, not a vendor lock-in decision.

Future adapters can support different provider APIs while still emitting the same Simplified Result Schema.

## Billing

Initial BYO-LLM policy:

```text
User pays their LLM provider directly.
Creator Dataset charges only Dataset access credits.
```

This avoids mixing:

- Dataset unlock economics
- model token economics

Later, the platform can optionally offer hosted AI credits as a separate product without changing Dataset entitlements.

## API

```text
POST   /api/saas/llm/connections
GET    /api/saas/llm/connections
DELETE /api/saas/llm/connections/{connection_id}

POST   /api/saas/datasets/{post_id}/organize
GET    /api/saas/llm/runs/{run_id}

GET    /api/saas/datasets/{post_id}/view
```

## Long-term Principle

Creator Dataset owns:

```text
data quality
provenance
completeness
access
versioning
```

The user's LLM owns:

```text
presentation
organization
summarization
knowledge extraction
```

Keeping those responsibilities separate is what makes the platform durable.
