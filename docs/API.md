# API Specification

Base path:

```text
/api
```

## 1. Import Creator

```http
POST /api/creators/import
Content-Type: application/json
```

Request:

```json
{
  "url": "https://www.xiaohongshu.com/user/profile/..."
}
```

Response:

```json
{
  "creator_id": "abc123",
  "job_id": "job_xxx",
  "status": "PENDING"
}
```

## 2. Creator Status

```http
GET /api/creators/{creator_id}/status
```

Response example:

```json
{
  "creator_id": "abc123",
  "name": "Creator",
  "status": "RUNNING",
  "posts": {
    "discovered": 537,
    "completed": 421,
    "partial": 5,
    "failed": 3
  },
  "comments": {
    "reported": 91763,
    "downloaded": 83412
  },
  "media": {
    "total": 2013,
    "downloaded": 1892
  },
  "completeness": 0.916
}
```

## 3. List Posts

```http
GET /api/creators/{creator_id}/posts
```

Query params:

- limit
- cursor
- status
- sort

## 4. Post Detail

```http
GET /api/posts/{post_id}
```

## 5. Post Comments

```http
GET /api/posts/{post_id}/comments
```

Query params:

- cursor
- limit
- root_only
- min_like_count

## 6. Comment Tree

```http
GET /api/posts/{post_id}/comment-tree
```

返回重建后的评论线程。

## 7. Retry / Repair

```http
POST /api/posts/{post_id}/repair-comments
```

用途：
- 重跑失败一级分页
- 重跑失败回复线程
- 对数量差异执行补抓

## 8. Resume Creator

```http
POST /api/creators/{creator_id}/resume
```

只调度非 COMPLETE 状态单元。

## 9. Export

```http
POST /api/creators/{creator_id}/export
```

Request:

```json
{
  "formats": ["jsonl", "markdown", "sqlite"],
  "include_media": true,
  "include_raw": false
}
```

## 10. Audit

```http
GET /api/posts/{post_id}/audit
```

Example:

```json
{
  "expected_comments": 2489,
  "actual_comments": 2471,
  "root_comments": 1203,
  "reply_comments": 1268,
  "root_pagination_finished": true,
  "reply_threads_total": 610,
  "reply_threads_finished": 607,
  "failed_threads": 3,
  "completeness_ratio": 0.9928,
  "status": "PARTIAL"
}
```

## 11. Error Shape

统一错误：

```json
{
  "error": {
    "code": "PLATFORM_BLOCKED",
    "message": "Authentication or platform risk control prevented collection.",
    "retryable": false
  }
}
```

建议错误码：

- INVALID_URL
- UNSUPPORTED_PLATFORM
- CREATOR_NOT_FOUND
- POST_NOT_FOUND
- AUTH_REQUIRED
- PLATFORM_BLOCKED
- RATE_LIMITED
- NETWORK_ERROR
- PARSE_ERROR
- MEDIA_DOWNLOAD_FAILED
- INTERNAL_ERROR
