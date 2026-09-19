# SaaS Access Architecture

## Product Model

Creator Dataset separates shared data infrastructure from user access rights.

```text
Shared Creator Dataset Layer
├── Creator
├── Posts
├── Comments
├── Media
├── OCR / STT
└── Dataset Artifacts

SaaS Access Layer
├── Users
├── API Keys
├── Roles
├── Credits
├── Entitlements
├── Creator Submissions
└── Billing Events
```

Two users unlocking the same Post do **not** create two copies of the Dataset.

The Dataset is generated once and access is granted independently through user entitlements.

## Roles

### Admin

Admin has unrestricted Dataset access and internal operational API access.

Admin can:

- create users
- create/revoke API keys
- promote/demote roles
- suspend/reactivate users
- grant free or paid credits
- inspect user balances and credit ledger
- use internal Job/Worker/Scheduler APIs
- repair Jobs
- access any Dataset

### Member

Members use the `/api/saas/*` surface.

Members can:

- submit a Creator
- inspect their own account
- inspect their entitlements
- unlock Post Datasets
- download unlocked Dataset artifacts

Members cannot directly invoke internal operational APIs when SaaS auth is enabled.

## Authentication

API keys are high-entropy secrets.

Only the SHA-256 digest is stored in the database. The full secret is returned only when the key is created.

Accepted headers:

```text
Authorization: Bearer cd_...
```

or:

```text
X-API-Key: cd_...
```

## Bootstrap Admin

For the first administrator:

```text
CREATOR_DATASET_SAAS_AUTH_ENABLED=true
CREATOR_DATASET_SAAS_BOOTSTRAP_ADMIN_KEY=<strong-secret>
```

Then create the first Admin through:

```http
POST /api/saas/admin/users
X-Bootstrap-Key: <strong-secret>
```

The response contains the administrator API key once.

After bootstrap, normal administration should use the Admin API key. The bootstrap secret can then be removed from deployment configuration.

## Free Dataset Credits

Default:

```text
5 free Dataset credits per Member
```

Configured through:

```text
CREATOR_DATASET_SAAS_DEFAULT_FREE_DATASET_CREDITS=5
```

Creating a Member writes a ledger grant:

```text
bucket=free
delta=+5
reason=signup_grant
```

## Dataset Unlock

```http
POST /api/saas/datasets/{post_id}/unlock
```

Resolution order:

```text
Admin?
  → unlimited

Existing entitlement?
  → allow, no charge

Free balance > 0?
  → free -1
  → create entitlement

Paid balance > 0?
  → paid -1
  → create entitlement

Otherwise
  → HTTP 402 PAYMENT_REQUIRED
```

Entitlements are unique by:

```text
user_id + platform + post_id
```

Therefore repeated unlock requests cannot double-charge the same Dataset.

## Shared Dataset Generation

Unlocking schedules a shared, idempotent Dataset Generation Job:

```text
dataset-generation:{platform}:{post_id}:{schema_version}
```

Multiple users may own entitlements to the same Dataset while the underlying Post processing is performed once.

A processing failure does not remove the entitlement. Repairing the Dataset does not consume another credit.

## Artifact Delivery

Successful Export registers shared Dataset artifacts:

- post.json
- comments.jsonl
- media.jsonl
- analysis.jsonl
- knowledge.md
- manifest.json

The registry stores object keys, not internal local filesystem paths.

### Local storage

Artifacts are streamed through an authenticated SaaS endpoint.

### S3 storage

The API returns short-lived presigned GET URLs.

## Internal API Guard

When:

```text
CREATOR_DATASET_SAAS_AUTH_ENABLED=true
```

non-`/api/saas/*` operational APIs require an Admin API key, except public health/readiness/capability endpoints.

This prevents Members from bypassing credits by directly calling internal Export or Job APIs.

## Main SaaS Endpoints

```text
POST /api/saas/admin/users
GET  /api/saas/admin/users
PATCH /api/saas/admin/users/{user_id}

POST /api/saas/admin/users/{user_id}/credits
GET  /api/saas/admin/users/{user_id}/credits

POST /api/saas/admin/users/{user_id}/api-keys
GET  /api/saas/admin/users/{user_id}/api-keys
POST /api/saas/admin/users/{user_id}/api-keys/{api_key_id}/revoke

GET  /api/saas/me
GET  /api/saas/me/entitlements

POST /api/saas/creators/submit

POST /api/saas/datasets/{post_id}/unlock
GET  /api/saas/datasets/{post_id}
GET  /api/saas/datasets/{post_id}/files/{artifact_name}
```

## Current Tenant Model

The current implementation is user-based rather than organization-based.

Future organization support can add:

```text
organizations
memberships
organization_roles
organization_credit_ledger
organization_entitlements
```

without changing the shared Creator Dataset layer.


## End-user Product Flow

The intended Member journey is now:

```text
Submit Creator URL
      ↓
202 Accepted
      ↓
CREATOR_IMPORT Durable Job
      ↓
Browse free Post Catalog
      ↓
Choose a Post
      ↓
Unlock Dataset
      ↓
free credit / paid credit
      ↓
shared Dataset Generation Job
      ↓
Dataset Ready
      ↓
authenticated download
```

### 1. Submit Creator

```http
POST /api/saas/creators/submit
```

Creator submission is asynchronous. The API only validates/resolves the URL and enqueues a shared `CREATOR_IMPORT` Job.

The same Creator submitted by multiple users shares the same underlying import Job.

Check:

```http
GET /api/saas/creators/{creator_id}/status
```

Large Creators are imported in bounded batches. If more Post pages remain, the Worker schedules an immediate continuation from the persisted cursor rather than falsely marking the import complete.

### 2. My Creators

```http
GET /api/saas/me/creators
```

Member workspaces only expose Creators that the user has submitted.

### 3. Browse Post Catalog — Free

```http
GET /api/saas/creators/{creator_id}/posts
```

Catalog browsing does not consume Dataset credits.

Each Post includes safe preview metadata plus:

- unlocked
- dataset_ready
- unlock_cost_credits
- can_unlock

Full body/OCR/STT/comments remain behind Dataset entitlement.

### 4. Unlock

```http
POST /api/saas/datasets/{post_id}/unlock
```

This is the billing boundary.

### 5. Poll Dataset State

```http
GET /api/saas/datasets/{post_id}
```

If processing is incomplete, the response exposes the shared generation Job status.

If ready, it returns authenticated download endpoints or short-lived S3 URLs.

## Production Security

When `environment=production`, readiness fails if SaaS authentication is disabled.

Bootstrap Admin secret comparison uses constant-time comparison.

For production:

- terminate TLS at the ingress/load balancer,
- keep API keys and bootstrap secrets in a secret manager,
- remove the bootstrap secret after the first persistent Admin is created,
- never expose internal operational APIs to Members.
