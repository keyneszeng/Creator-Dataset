# Data Model

## 1. creators

```sql
CREATE TABLE creators (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    name TEXT,
    profile_url TEXT,
    avatar_url TEXT,
    bio TEXT,
    follower_count INTEGER,
    following_count INTEGER,
    discovered_post_count INTEGER,
    raw_json TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE(platform, creator_id)
);
```

## 2. posts

```sql
CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    content TEXT,
    post_type TEXT,
    published_at DATETIME,
    like_count INTEGER,
    favorite_count INTEGER,
    share_count INTEGER,
    reported_comment_count INTEGER,
    downloaded_comment_count INTEGER,
    comment_status TEXT,
    raw_json TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE(platform, post_id)
);
```

## 3. comments

```sql
CREATE TABLE comments (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    comment_id TEXT NOT NULL,
    root_comment_id TEXT,
    parent_comment_id TEXT,
    user_id TEXT,
    user_name TEXT,
    user_avatar TEXT,
    content TEXT,
    like_count INTEGER,
    ip_location TEXT,
    published_at DATETIME,
    depth INTEGER DEFAULT 0,
    has_more_replies BOOLEAN,
    reply_count INTEGER,
    raw_json TEXT,
    created_at DATETIME,
    UNIQUE(platform, comment_id)
);
```

### 关系语义

一级评论：

```text
comment_id = C1
root_comment_id = C1
parent_comment_id = NULL
depth = 0
```

回复：

```text
comment_id = C2
root_comment_id = C1
parent_comment_id = C1
depth = 1
```

若平台提供更深层真实父子关系，则继续保存，不将 Schema 锁死为两层。

## 4. media

```sql
CREATE TABLE media (
    id INTEGER PRIMARY KEY,
    platform TEXT,
    post_id TEXT,
    comment_id TEXT,
    media_type TEXT,
    remote_url TEXT,
    local_path TEXT,
    sha256 TEXT,
    width INTEGER,
    height INTEGER,
    duration REAL,
    download_status TEXT,
    created_at DATETIME
);
```

media_type：

- image
- video
- audio
- cover
- comment_image

## 5. jobs

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    job_type TEXT NOT NULL,
    platform TEXT,
    creator_id TEXT,
    post_id TEXT,
    comment_id TEXT,
    status TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    next_retry_at DATETIME,
    created_at DATETIME,
    started_at DATETIME,
    completed_at DATETIME
);
```

## 6. crawl_audits

```sql
CREATE TABLE crawl_audits (
    id INTEGER PRIMARY KEY,
    post_id TEXT NOT NULL,
    expected_comments INTEGER,
    actual_comments INTEGER,
    root_comments INTEGER,
    reply_comments INTEGER,
    failed_threads INTEGER,
    root_pagination_finished BOOLEAN,
    reply_threads_total INTEGER,
    reply_threads_finished INTEGER,
    pagination_finished BOOLEAN,
    completeness_ratio REAL,
    status TEXT,
    notes TEXT,
    audited_at DATETIME
);
```

## 7. Raw Response Policy

所有关键对象都必须保留 raw_json：

- creator
- post
- comment

对于分页 API，建议额外将原始响应按时间和 cursor 存档，例如：

```text
raw/
└── posts/
    └── <post_id>/
        ├── detail.json
        └── comments/
            ├── root_cursor_000.json
            ├── root_cursor_001.json
            └── replies_<comment_id>_000.json
```

## 8. 唯一性与幂等

最低唯一键：

- Creator: (platform, creator_id)
- Post: (platform, post_id)
- Comment: (platform, comment_id)

写入应优先 UPSERT。

## 9. Export Schema

all_posts.jsonl 每行一个标准化 Post。

all_comments.jsonl 每行一个标准化 Comment，并包含：

```json
{
  "platform": "xiaohongshu",
  "post_id": "...",
  "comment_id": "...",
  "root_comment_id": "...",
  "parent_comment_id": "...",
  "depth": 0,
  "user": {
    "id": "...",
    "name": "..."
  },
  "content": "...",
  "like_count": 0,
  "published_at": "...",
  "source": {
    "creator_id": "...",
    "post_url": "..."
  }
}
```
