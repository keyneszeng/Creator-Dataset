# System Architecture

## 1. 总体架构

```text
                    Client
                      │
                      ▼
                FastAPI API
                      │
            ┌─────────┴─────────┐
            │                   │
       URL Resolver         Query / Export
            │
            ▼
      PlatformAdapter
            │
            ▼
      Creator Discovery
            │
            ▼
         Job Engine
            │
   ┌────────┼───────────────┬──────────────┐
   ▼        ▼               ▼              ▼
Post      Media          Comments        Audit
Worker    Worker          Worker          Worker
   │        │               │              │
   └────────┴───────────────┴──────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
       SQLite                 Filesystem
          │                       │
          ▼                       ▼
   normalized data           raw/media files
```

## 2. PlatformAdapter

核心接口建议：

```python
from typing import Protocol, AsyncIterator

class PlatformAdapter(Protocol):
    async def resolve_creator(self, url: str): ...
    async def get_creator(self, creator_id: str): ...
    async def iter_posts(self, creator_id: str) -> AsyncIterator[dict]: ...
    async def get_post(self, post_id: str): ...
    async def iter_root_comments(self, post_id: str) -> AsyncIterator[dict]: ...
    async def iter_replies(self, post_id: str, root_comment_id: str) -> AsyncIterator[dict]: ...
    async def download_media(self, url: str, target_path: str): ...
```

V0.1：

```text
PlatformAdapter
└── XiaohongshuAdapter
```

后续：

```text
PlatformAdapter
├── XiaohongshuAdapter
├── WechatAdapter
├── DouyinAdapter
└── BilibiliAdapter
```

## 3. Job 拆分

严禁单一 crawl_creator() 长任务。

建议：

```text
CreatorDiscoveryJob
       │
       ▼
PostDiscoveryJob
       │
       ├── PostDetailJob
       ├── MediaDownloadJob
       ├── RootCommentJob
       │       └── SubCommentJob
       └── ValidationJob
```

每个 Post 独立持久化状态。

## 4. 数据流

```text
Platform response
      │
      ├── raw JSON
      │
      └── normalization
              │
              ├── creators
              ├── posts
              ├── comments
              ├── media
              └── audits
```

Raw data 永远优先保存，再做字段映射。

## 5. Retry 策略

错误分类：

### RETRYABLE

- 网络超时
- HTTP 429
- 临时 5xx
- 临时解析失败
- 媒体下载失败

策略：
- 指数退避
- jitter
- 最大重试次数
- next_retry_at

### BLOCKED

- 登录失效
- Captcha
- 风控
- 明确权限不足

策略：
- 停止高频重试
- 标记 BLOCKED
- 等待登录态恢复 / 人工处理

### PERMANENT

- 内容已删除
- URL 永久失效
- 明确无权限

策略：
- FAILED 或 unavailable 标记
- 保留原错误

## 6. 并发原则

V0.1 默认保守：

- Creator discovery：1 worker
- Post detail：低并发
- Comments：低并发 + delay
- Media：可比 API 请求更高并发

不要以吞吐量优先于稳定性。

## 7. Storage

建议目录：

```text
data/
└── xiaohongshu/
    └── <creator_id>/
        ├── creator.json
        ├── database.sqlite
        ├── raw/
        ├── posts/
        │   └── <post_id>/
        │       ├── post.json
        │       ├── content.md
        │       ├── raw.json
        │       ├── images/
        │       ├── video/
        │       └── comments/
        │           ├── comments.jsonl
        │           ├── threads.json
        │           └── images/
        └── export/
            ├── all_posts.jsonl
            └── all_comments.jsonl
```

## 8. Suggested Repository Structure

```text
app/
├── api/
├── core/
│   ├── database.py
│   ├── jobs.py
│   ├── retry.py
│   └── settings.py
├── platforms/
│   ├── base.py
│   └── xiaohongshu/
│       ├── adapter.py
│       ├── auth.py
│       ├── creator.py
│       ├── posts.py
│       ├── comments.py
│       └── media.py
├── models/
├── workers/
└── audit/
    └── completeness.py

tests/
web/
data/
```

## 9. 安全与合规边界

架构上不提供以下能力：

- 绕过登录、付费墙或访问控制
- 破解验证码
- 获取私密/仅好友可见内容
- 隐藏采集身份的攻击性基础设施
- 未经授权的大规模个人敏感信息收集

采集层应支持限速、停止、错误审计和数据最小化。
