# Engineering Roadmap

## Milestone 0 — Repository Foundation

目标：
- 项目结构
- 配置系统
- SQLite 初始化
- 日志
- 基础测试
- PlatformAdapter interface

Done when：
- 能启动 FastAPI
- 能连接 SQLite
- 能创建最小数据表
- 能运行测试

## Milestone 1 — URL → Creator

实现：

```text
Xiaohongshu Creator URL
  ↓
resolve_creator
  ↓
creator_id
  ↓
creator profile
```

验收：
- 正常主页 URL
- 带 query 参数 URL
- 分享链接（若可公开解析）
- 无效 URL 有明确错误

## Milestone 2 — Creator → All Discoverable Posts

实现分页枚举。

验收：
- 记录 cursor
- 支持断点
- UPSERT
- 重复执行不重复
- discovery 完成状态可审计

## Milestone 3 — Post Detail

获取并标准化：

- title
- content
- published_at
- metrics
- media URLs
- reported_comment_count
- raw JSON

## Milestone 4 — Media

实现：

- 图片
- 视频
- Cover
- SHA256
- 下载状态
- 重试
- 已下载文件去重

## Milestone 5 — Root Comments

实现一级评论分页。

验收：
- cursor 持久化
- has_more 耗尽
- comment UPSERT
- raw page 保存
- 中断后恢复

## Milestone 6 — Replies

对每个 root comment：

- 判断是否有更多回复
- 分页拉取
- 保存 root_comment_id
- 保存 parent_comment_id
- 保存线程完成状态

## Milestone 7 — Comment Media

下载评论图片，并绑定 comment_id。

## Milestone 8 — Completeness Audit

实现：

```text
reported count
vs
unique downloaded count
vs
pagination state
vs
failed threads
```

输出：

- COMPLETE
- PARTIAL
- BLOCKED
- FAILED

## Milestone 9 — Retry / Resume

实现：

- exponential backoff
- retry_count
- next_retry_at
- Resume Creator
- Repair Missing Comments

## Milestone 10 — Export

输出：

- SQLite
- posts.jsonl
- comments.jsonl
- Markdown
- media directory

## Milestone 11 — Minimal Web UI

仅三个页面：

1. Import Creator
2. Creator progress
3. Post + comment tree

## V0.1 Release Criteria

必须全部满足：

- 一个 Creator URL 可创建采集任务
- 可以发现全部当前可访问公开 Post
- 每篇 Post 有独立任务状态
- 支持一级评论分页
- 支持二级回复分页
- 评论与 Post / Parent 对应关系正确
- 支持媒体文件
- 支持断点续传
- 支持完整度审计
- 支持 JSONL / SQLite 导出
- 不因单一 Post 失败导致 Creator 全任务失败

## V0.2

微信公众号 Adapter：

- 公众号识别
- 历史文章
- 正文 / 图片 / 视频
- 公开可获取评论
- Comment media
- 统一 Schema

## V0.3

Enrichment：

- OCR
- STT
- Markdown normalization
- language detection
- content fingerprint
- duplicate detection

## V1

Knowledge Layer：

- Topic extraction
- FAQ
- Creator answers
- User pain points
- Product signals
- semantic search
- RAG
