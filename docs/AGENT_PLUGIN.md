# Creator Dataset Agent Plugin

## Product Direction

Creator Dataset is Agent-first.

The primary end-user interface is ChatGPT / Codex / another MCP-capable Agent, not a standalone Member dashboard.

```text
User
  ↓
ChatGPT / Agent
  ↓
Creator Dataset Plugin
├── Skill
└── MCP Server
      ↓
Creator Dataset Core
├── Creator import
├── Posts
├── Comments
├── Media
├── OCR / STT
├── Dataset generation
├── Local/free access
└── Optional future commercial modules
```

The current Agent product is fully free for personal use. Existing SaaS/Billing code is retained only as dormant future infrastructure and is not part of the current user flow.

## Plugin Layout

```text
plugins/creator-dataset/
├── plugin.json
├── mcp.json
└── skills/
    └── creator-research/
        ├── SKILL.md
        └── agents/
            └── openai.yaml
```

The Skill teaches the Agent when and how to use the MCP tools.

The MCP server performs live data access and controlled actions.

## Agent-facing MCP Tools

The first tool surface is deliberately small:

```text
account_status
creator_submit
creator_status
creator_posts
dataset_prepare
dataset_status
dataset_get
dataset_content
dataset_comments
```

Internal implementation details such as Job DAGs, checkpoint cursors, OCR engine settings, storage keys, and raw API responses are not exposed as normal Agent tools.

## Local Runtime

Install the Agent extra:

```bash
pip install -e ".[agent,xhs,ocr,stt]"
```

Start the normal Worker:

```bash
creator-dataset-worker
```

Then start the MCP server:

```bash
creator-dataset-mcp
```

Default endpoint:

```text
http://127.0.0.1:8765/mcp
```

The server uses MCP Streamable HTTP.

## Test with MCP Inspector

Use the MCP Inspector against:

```text
http://127.0.0.1:8765/mcp
```

Verify:

1. server discovery succeeds;
2. the nine compact tools are listed;
3. `account_status` works;
4. `creator_submit` returns a background import state;
5. `dataset_prepare` prepares a Dataset without credits or payment.

## ChatGPT Development Practice

A browser-hosted ChatGPT session cannot directly reach a loopback MCP endpoint.

For ChatGPT development testing:

1. run Creator Dataset MCP locally;
2. expose it using the supported secure MCP tunnel/development connection mechanism;
3. obtain the HTTPS MCP endpoint;
4. build a Plugin bundle pointing at that endpoint;
5. install/import the Plugin in ChatGPT's Plugin development flow;
6. test in a fresh conversation.

Build the bundle:

```bash
creator-dataset-plugin-build \
  --mcp-url https://YOUR-MCP-ENDPOINT/mcp
```

Output:

```text
dist/plugins/creator-dataset/
```

For localhost-only testing:

```bash
creator-dataset-plugin-build \
  --mcp-url http://127.0.0.1:8765/mcp \
  --allow-local-http
```

Do not publish a Plugin with a localhost URL.

## Test Prompts in ChatGPT

### Import

```text
研究这个小红书博主：
https://www.xiaohongshu.com/user/profile/...
```

Expected Agent behavior:

```text
creator_submit
→ creator_status
→ concise progress/result
```

### Browse

```text
给我看看这个博主最近有哪些值得研究的内容。
```

Expected:

```text
creator_posts
```

Catalog browsing is free.

### Prepare Dataset

```text
把第 2 篇做成完整 Dataset。
```

That is explicit user intent, so the Agent may call:

```text
dataset_unlock(post_id, confirm=true)
```

If the user merely asks which Post might be useful, do not unlock it.

### Analyze

```text
总结这篇的核心观点以及评论区最常见的问题。
```

Expected:

```text
dataset_get
↓
dataset_content if more evidence is needed
↓
dataset_comments if more comment pages are needed
↓
ChatGPT performs the analysis itself
```

A separate server-side LLM is not required for the normal Plugin workflow.

## Free-mode Policy

Current default:

```text
CREATOR_DATASET_AGENT_FREE_MODE=true
```

In this mode:

- Creator import is free;
- Post catalog browsing is free;
- Dataset preparation is free;
- Dataset reading is free;
- comment pagination is free;
- no credits are consumed;
- no payment flow is exposed to the Agent.

A real Member identity may still be used for workspace isolation and future compatibility, but Dataset preparation grants a `free_mode` entitlement without touching the credit ledger.

Commercial billing, payment orders, and WeChat Pay code remain dormant for possible future productization.

## Remote Authentication Boundary

The current MCP server intentionally binds to loopback by default:

```text
127.0.0.1
```

It refuses a non-loopback MCP bind before remote identity/OAuth support is implemented.

This prevents accidentally publishing a local-Admin MCP server to the Internet.

Public Plugin deployment must add OAuth 2.1 user identity mapping so each MCP request resolves to the correct Creator Dataset user and entitlements.

A secure development tunnel is for testing; it is not the final public authentication architecture.

## Production Plugin

Public release target:

```text
ChatGPT
  ↓
OAuth 2.1
  ↓
https://creator-dataset.example/mcp
  ↓
Member identity
  ↓
User/workspace authorization
  ↓
Creator Dataset
```

Production MCP requirements:

- stable public HTTPS endpoint;
- Streamable HTTP;
- OAuth 2.1 for user-specific/private data;
- rate limiting;
- per-user authorization;
- audit logs;
- no local-Admin fallback;
- stable tool schemas.

## Why the Skill Matters

MCP tools answer “what can the Agent do?”

The Skill answers “when should it do it?”

Examples encoded in the Skill:

- browsing a Creator is free;
- Dataset preparation is free;
- distinguish author/OCR/STT/comment provenance;
- do not claim an incomplete import is complete;
- prefer compact Dataset results before fetching larger evidence;
- let ChatGPT perform normal organization and reasoning itself.

That workflow logic is the core Agent-native product experience.
