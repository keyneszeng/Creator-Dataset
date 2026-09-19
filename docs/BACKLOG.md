# Initial Engineering Backlog

本 Backlog 对应 V0.1：小红书 Creator URL → 完整可恢复 Dataset。

## P0 — Repository Foundation

- [ ] 初始化 Python 3.12 项目
- [ ] FastAPI app skeleton
- [ ] Settings / env 管理
- [ ] SQLite connection / migration
- [ ] structured logging
- [ ] pytest
- [ ] PlatformAdapter protocol
- [ ] Job status enum
- [ ] 基础 CI

## P0 — Xiaohongshu URL Resolver

- [ ] 识别小红书 Creator profile URL
- [ ] 解析 creator_id
- [ ] 规范化 canonical URL
- [ ] 错误分类
- [ ] 单元测试

验收：

```text
input: creator profile URL
output: platform + creator_id + canonical_url
```

## P0 — Authentication Boundary

- [ ] 定义 CredentialProvider interface
- [ ] Cookie 导入
- [ ] 登录态检查
- [ ] AUTH_REQUIRED
- [ ] BLOCKED 状态
- [ ] 不在日志打印 Cookie / token

## P0 — Creator Discovery

- [ ] 获取 Creator profile
- [ ] 保存 raw creator response
- [ ] creators UPSERT
- [ ] Creator refresh

## P0 — Post Discovery

- [ ] 分页枚举 Creator posts
- [ ] 保存 cursor/checkpoint
- [ ] posts UPSERT
- [ ] 保存 raw pagination response
- [ ] discovery_finished flag
- [ ] 支持 resume

## P0 — Post Detail

- [ ] title/content
- [ ] published_at
- [ ] post_type
- [ ] metrics
- [ ] media URLs
- [ ] reported_comment_count
- [ ] raw_json

## P0 — Root Comments

- [ ] root comments cursor pagination
- [ ] raw pages archive
- [ ] comment UPSERT
- [ ] pagination checkpoint
- [ ] root_pagination_finished
- [ ] retry / rate-limit handling

## P0 — Replies

- [ ] 找出存在回复的 root comments
- [ ] replies cursor pagination
- [ ] root_comment_id
- [ ] parent_comment_id
- [ ] reply thread checkpoint
- [ ] failed thread tracking

## P0 — Completeness Audit

- [ ] expected_comments
- [ ] actual unique comments
- [ ] root_comments
- [ ] reply_comments
- [ ] reply_threads_total
- [ ] reply_threads_finished
- [ ] failed_threads
- [ ] completeness_ratio
- [ ] COMPLETE/PARTIAL decision

注意：平台展示评论数与 API 可访问评论数可能不完全一致，因此保留差异，不伪造“100%”。

## P1 — Media

- [ ] Post images
- [ ] Video
- [ ] Cover
- [ ] Comment images
- [ ] sha256
- [ ] download retry
- [ ] download status
- [ ] local path convention

## P1 — Job Engine

- [ ] jobs table
- [ ] enqueue
- [ ] claim
- [ ] retry
- [ ] exponential backoff
- [ ] next_retry_at
- [ ] resume creator
- [ ] repair comments

## P1 — API

- [ ] POST /api/creators/import
- [ ] GET /api/creators/{id}/status
- [ ] GET /api/creators/{id}/posts
- [ ] GET /api/posts/{id}
- [ ] GET /api/posts/{id}/comments
- [ ] GET /api/posts/{id}/comment-tree
- [ ] POST /api/posts/{id}/repair-comments
- [ ] POST /api/creators/{id}/resume
- [ ] GET /api/posts/{id}/audit

## P1 — Export

- [ ] all_posts.jsonl
- [ ] all_comments.jsonl
- [ ] Markdown per post
- [ ] SQLite export
- [ ] Media directory
- [ ] manifest.json

## P1 — Test Fixtures

建立脱敏 fixtures：

- [ ] creator
- [ ] post list page
- [ ] post detail
- [ ] root comment page
- [ ] sub-comment page
- [ ] has_more false
- [ ] deleted/unavailable content
- [ ] rate-limit error
- [ ] auth failure

测试不得依赖实时平台请求作为唯一验证方式。

## P2 — Minimal UI

- [ ] URL import page
- [ ] Creator progress page
- [ ] Post detail page
- [ ] comment tree
- [ ] Resume
- [ ] Repair Missing
- [ ] Export

## Definition of Done

一个功能只有在以下条件全部满足时才算完成：

- 有明确输入/输出
- 有持久化状态
- 失败不会破坏已有数据
- 支持重复调用
- 有错误分类
- 有至少基础测试
- 不泄露认证信息
- raw response 可追溯（适用时）
- README / docs 同步更新（接口变化时）
