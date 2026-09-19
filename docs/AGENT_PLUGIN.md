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
├── Credits / Entitlements
└── Billing
```

The existing SaaS APIs remain useful as the service boundary behind the Agent integration and for Admin/Billing operations.

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
dataset_unlock
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
5. `dataset_unlock(confirm=false)` never silently unlocks a new Dataset.

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

Catalog browsing must not consume credits.

### Unlock

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

## Unlock Safety

Unlocking is a controlled write/payment action.

The MCP tool has:

```text
confirm=false
```

by default.

Without explicit confirmation it only returns a preview:

```text
CONFIRMATION_REQUIRED
credit_cost
free_credits
paid_credits
```

The Skill instructs the Agent not to consume a credit just because more data might improve an answer.

## Local Admin vs Real Member Testing

Default local MCP mode runs as a local Admin principal for development.

Admin still needs explicit Agent unlock intent, but the credit cost is zero.

To test the real five-free-credit Member flow, create a Member API key and configure:

```text
CREATOR_DATASET_MCP_USER_API_KEY=cd_...
```

MCP tool calls then run as that Member.

This lets ChatGPT exercise:

```text
5 free unlocks
→ paid credit balance
→ PAYMENT_REQUIRED
```

without changing MCP tool schemas.

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
Credits / Entitlements
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
- do not automatically unlock Posts;
- distinguish author/OCR/STT/comment provenance;
- do not claim an incomplete import is complete;
- prefer compact Dataset results before fetching larger evidence;
- let ChatGPT perform normal organization and reasoning itself.

That workflow logic is the core Agent-native product experience.
