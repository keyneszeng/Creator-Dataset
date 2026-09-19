# Comment Crawling

## Goal

For every imported Post, capture all currently accessible public comments while preserving reply relationships and proving how complete the crawl was.

The system distinguishes:

- platform-reported comment count
- unique comments actually persisted
- root pagination completion
- reply-thread pagination completion
- failed threads

## Flow

```text
Post
  ↓
Root Comments
  ↓
cursor pagination until has_more=false
  ↓
persist root comments
  ↓
find roots with replies
  ↓
for each root:
    sub-comment cursor pagination
  ↓
persist replies with:
    root_comment_id
    parent_comment_id
    depth
  ↓
Audit
```

## Checkpoints

Root comments:

```text
scope = root_comments
object_id = <post_id>
```

Replies:

```text
scope = sub_comments
object_id = <post_id>:<root_comment_id>
```

This makes each reply thread independently resumable.

## Completeness

The audit records:

- expected_comments
- actual_comments
- root_comments
- reply_comments
- failed_threads
- root_pagination_finished
- reply_threads_total
- reply_threads_finished
- pagination_finished
- completeness_ratio
- status

A crawl is marked `COMPLETE` only when:

1. root pagination is exhausted,
2. every discovered reply thread is exhausted,
3. no reply thread failed.

The ratio is informational. A difference between the platform-displayed count and accessible API data does not automatically mean pagination failed because moderation, deletion or visibility rules may affect the displayed total.

## API

```http
POST /api/posts/{post_id}/crawl-comments
```

Example body:

```json
{
  "max_root_pages": 200,
  "max_reply_pages": 200
}
```

Example response:

```json
{
  "post_id": "note-id",
  "root_comments": 1052,
  "reply_comments": 1318,
  "failed_threads": 0,
  "status": "COMPLETE",
  "completeness_ratio": 0.9928
}
```

## Important limitation

"COMPLETE" means all pagination endpoints accessible to the current authenticated session were exhausted. It does not claim that deleted, hidden, moderated, private, or otherwise inaccessible comments were obtained.
