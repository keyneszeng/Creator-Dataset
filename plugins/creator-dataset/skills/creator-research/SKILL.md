---
name: creator-research
description: Research a public Creator from a profile URL, browse their content catalog, prepare structured Creator Datasets for free, and analyze author content and public discussion.
---

Use the `creator-dataset` MCP tools as the data layer for public Creator research.

## Core workflow

When the user provides a Creator profile URL or asks to research a Creator:

1. Call `creator_submit` with the URL.
2. Call `creator_status`.
3. If import is still running, explain that discovery is in progress. Do not pretend the catalog is complete.
4. Once Posts are available, call `creator_posts` and present a concise selection.
5. Browsing the catalog is free.

## Dataset preparation

Dataset preparation is currently free.

- When deeper evidence is useful, call `dataset_prepare` for the relevant Post.
- No credit or payment confirmation is required.
- Do not mention credits, pricing, paywalls, or payment unless the user explicitly asks about future commercial plans.
- Preparing the same Dataset repeatedly is safe because generation is idempotent.

## Reading a Dataset

After preparation:

1. Call `dataset_status`.
2. If it is not ready, report the current state without inventing missing content.
3. When ready, call `dataset_get` first.
4. Use the compact result to answer straightforward questions.
5. Only call `dataset_content` when deeper evidence, OCR/transcript text, or broader comment context is needed.
6. Use `dataset_comments` for additional comment pages instead of requesting an unnecessarily large payload.

## Analysis behavior

ChatGPT is the organization and reasoning layer. Use the returned Dataset to perform the user's requested analysis directly.

Examples:
- summarize the Creator's position;
- compare several unlocked Posts;
- extract reusable knowledge;
- identify recurring audience questions;
- synthesize comment sentiment or disagreement;
- turn findings into notes, reports, or structured outputs.

Do not require a separate server-side LLM organization run unless the user specifically asks for it.

## Provenance and completeness

Treat author text, OCR, transcripts, comments, and replies as different provenance classes.

Do not imply that:
- OCR text was written by the author;
- comments represent the Creator's own views;
- a partially imported Creator is complete;
- public comments are guaranteed to be 100% exhaustive.

When evidence matters, distinguish the source type in the answer.

## Response style

Keep normal user responses simple.

Prefer:
- Creator name/topic and Post count;
- short Post lists;
- concise Dataset findings;
- simple preparation/readiness status only when relevant.

Do not expose Job IDs, storage keys, cursor values, checkpoint details, raw JSON, OCR engine names, or other implementation details unless the user asks for technical debugging.
