# Personal Cloud Deployment

This profile moves Creator Dataset off the laptop and turns it into one private cloud service for:

```text
ChatGPT / Agent  → /mcp
Web / Mini Program → /v1
Admin / Operations → /api
```

The current personal-use mode remains free.

## Topology

```text
Internet
   ↓
Caddy / HTTPS
   ↓
Creator Dataset
├── /mcp
├── /v1
└── /api
   ↓
PostgreSQL
   ↓
Worker + Scheduler
   ↓
R2 / S3-compatible Object Storage
```

## Requirements

- one Linux server with Docker + Docker Compose;
- one domain pointing to the server;
- one S3-compatible bucket such as Cloudflare R2;
- your own Xiaohongshu Cookie;
- a long random private Agent token.

## Configure

Clone the repository and create `.env`:

```bash
cp .env.example .env
```

Set at minimum:

```text
CREATOR_DATASET_XHS_COOKIE=...

CREATOR_DATASET_S3_BUCKET=...
CREATOR_DATASET_S3_REGION=auto
CREATOR_DATASET_S3_ENDPOINT_URL=https://...
CREATOR_DATASET_S3_ACCESS_KEY_ID=...
CREATOR_DATASET_S3_SECRET_ACCESS_KEY=...

CREATOR_DATASET_AGENT_FREE_MODE=true
```

Create deployment secrets in the shell or a server secret file:

```bash
export CREATOR_DATASET_DOMAIN=creator.example.com
export POSTGRES_PASSWORD='use-a-long-random-password'
export CREATOR_DATASET_CLOUD_AGENT_TOKEN='use-a-long-random-agent-token'
```

The domain's DNS A/AAAA record must point to the server.

## Start

```bash
docker compose -f deploy/cloud-personal/docker-compose.yml up -d --build
```

Caddy obtains and renews HTTPS certificates automatically when DNS and ports 80/443 are reachable.

## Verify

Public health/readiness:

```bash
curl https://$CREATOR_DATASET_DOMAIN/api/health

curl https://$CREATOR_DATASET_DOMAIN/api/system/readiness
```

Private REST:

```bash
curl \
  -H "Authorization: Bearer $CREATOR_DATASET_CLOUD_AGENT_TOKEN" \
  https://$CREATOR_DATASET_DOMAIN/v1/account
```

MCP endpoint:

```text
https://creator.example.com/mcp
```

It uses the same private Bearer token.

## Build the remote Plugin

From any machine with the repository installed:

```bash
creator-dataset-plugin-build \
  --mcp-url https://creator.example.com/mcp
```

For remote Plugin bundles, the builder declares:

```text
bearer_token_env_var=CREATOR_DATASET_CLOUD_AGENT_TOKEN
```

The secret itself is never written into the Plugin bundle.

## Current Security Model

This profile is intentionally single-user/personal:

```text
one private token
→ your Agent
→ full personal free-mode access
```

Do not share the token.

Before opening the service to multiple users, replace this personal-token model with OAuth 2.1 and per-user authorization.

## Mini Program / Web

The same server already exposes compact REST endpoints:

```text
GET  /v1/account
POST /v1/creators
GET  /v1/creators/{creator_id}
GET  /v1/creators/{creator_id}/posts
POST /v1/datasets/{post_id}/prepare
GET  /v1/datasets/{post_id}
GET  /v1/datasets/{post_id}/status
GET  /v1/datasets/{post_id}/content
GET  /v1/datasets/{post_id}/comments
```

A future WeChat Mini Program can be a thin client over these endpoints while ChatGPT continues using MCP.

## Backup

PostgreSQL:

```bash
docker compose -f deploy/cloud-personal/docker-compose.yml \
  exec api creator-dataset-backup --output /app/data/backups
```

Object media lives in the configured S3/R2 bucket and should use provider retention/versioning policies.
