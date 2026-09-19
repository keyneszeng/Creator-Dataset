# Creator Dataset

将公开 Creator 内容转换为结构化、可审计、可供 AI 使用的数据集。

## V0.1 目标

V0.1 首先支持 **小红书 Creator 主页 URL**：

```text
Creator URL
  ↓
识别 Creator
  ↓
发现全部公开笔记
  ↓
下载正文 / 图片 / 视频 / 元数据
  ↓
抓取全部可获取一级评论
  ↓
抓取全部可获取二级回复
  ↓
评论图片
  ↓
断点续传 + 重试 + 完整度审计
  ↓
SQLite + JSONL + Markdown + Media
```

核心目标不是“做一个爬虫”，而是：

> **URL → Creator Dataset**

## 设计原则

1. **平台适配器化**：Crawler 与核心数据层解耦，后续可接入微信公众号、抖音、B站、知乎等。
2. **Raw First**：保留平台原始 JSON，标准化数据只是派生层。
3. **可恢复**：任何任务都可断点续传，单条失败不影响整个 Creator。
4. **可审计**：不轻易声称“100% 全量”，记录平台显示数量、实际获取数量、分页状态与差异。
5. **评论是一等数据**：评论、回复、评论图片及其上下文关系必须结构化保存。
6. **先 Dataset，后 AI**：V0.1 不做 RAG、Embedding、Agent，先保证数据采集与完整性。

## 当前实现状态

已完成 Milestone 0 的第一批工程骨架：

- FastAPI 应用入口
- SQLite 核心 Schema
- Settings / 数据目录初始化
- PlatformAdapter 协议
- JobStatus / JobType
- XiaohongshuAdapter skeleton
- 小红书 Creator URL Resolver
- Resolver / Database / API 基础测试
- GitHub Actions CI

当前已可将标准小红书 Creator 主页 URL：

```text
https://www.xiaohongshu.com/user/profile/<creator_id>
```

规范化为：

```json
{
  "platform": "xiaohongshu",
  "creator_id": "<creator_id>",
  "canonical_url": "https://www.xiaohongshu.com/user/profile/<creator_id>"
}
```

下一阶段是接入真实 Creator Profile / Post Discovery。

## 本地开发

要求 Python 3.12+。

```bash
python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev,xhs,ocr,stt]"

uvicorn app.main:app --reload
```

服务启动后，另开一个终端启动 Durable Worker：

```bash
creator-dataset-worker
```

关键接口：

```text
GET  /api/health
GET  /api/system/status
POST /api/creators/resolve
POST /api/creators/import
POST /api/creators/{creator_id}/enqueue-pipeline
GET  /api/jobs/{job_id}/progress
```

配置小红书登录态：

```bash
cp .env.example .env
# 在 .env 中填写你自己的 CREATOR_DATASET_XHS_COOKIE
```

导入 Creator：

```bash
curl -X POST http://127.0.0.1:8000/api/creators/import \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.xiaohongshu.com/user/profile/<creator_id>","max_pages":20}'
```

运行测试：

```bash
pytest
```

## 文档

- [产品与范围](docs/PRD.md)
- [系统架构](docs/ARCHITECTURE.md)
- [数据模型](docs/DATA_MODEL.md)
- [API 设计](docs/API.md)
- [研发路线图](docs/ROADMAP.md)
- [开源依赖与参考项目](docs/OPEN_SOURCE_REFERENCES.md)
- [首批研发 Backlog](docs/BACKLOG.md)
- [认证与 Cookie 边界](docs/AUTHENTICATION.md)
- [当前实现状态](docs/IMPLEMENTATION_STATUS.md)
- [OCR Pipeline](docs/OCR.md)
- [Media Pipeline](docs/MEDIA_PIPELINE.md)
- [Video STT](docs/STT.md)
- [Analysis Corpus](docs/ANALYSIS_CORPUS.md)
- [Reliability Architecture](docs/RELIABILITY_ARCHITECTURE.md)
- [Stage Jobs](docs/STAGE_JOBS.md)
- [Incremental Refresh](docs/INCREMENTAL_REFRESH.md)
- [Refresh Scheduler](docs/SCHEDULER.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Backup & Restore](docs/BACKUP_RESTORE.md)
- [Creator Pipeline](docs/CREATOR_PIPELINE.md)

## V0.1 技术建议

- Python 3.12
- FastAPI
- SQLite
- SQLite durable queue + Worker lease（V0.x 单机阶段）
- Postgres / distributed queue（多机阶段）
- Next.js（管理 UI，可后置）
- 本地文件系统（V0.1 Media Storage）

## V0.1 明确不做

- 向量数据库
- Embedding
- RAG
- AI Chat
- 自动知识图谱
- 小程序
- 多平台同时首发

这些能力建立在可靠 Dataset 之上，放到后续版本。

## 合规与使用边界

本项目定位为对**公开可访问内容**的归档、数据工程与研究基础设施。使用者应遵守适用法律、平台条款、版权规则、隐私要求和访问频率限制。不得将本项目用于绕过访问控制、获取非公开数据或未经授权的大规模个人信息收集。

## License

待确定。


## 当前数据处理链路

```text
Creator URL
  ↓
Creator + Posts
  ↓
Post Detail
  ↓
Post Media / Comment Media
  ↓
Download + SHA256
  ↓
OCR + Video STT
  ↓
Comments + Replies
  ↓
Audit
  ↓
JSON / JSONL / Markdown Dataset
```

常用接口：

```text
POST /api/creators/import
POST /api/creators/{creator_id}/enrich-posts
POST /api/creators/{creator_id}/enqueue-pipeline
GET  /api/jobs/{job_id}/progress
POST /api/creators/{creator_id}/run-pipeline   # 仅建议本地调试
POST /api/posts/{post_id}/crawl-comments
POST /api/posts/{post_id}/process-media
POST /api/posts/{post_id}/export
```


## 长期运行模式

生产默认不要用同步 `run-pipeline` 长时间占用 HTTP 请求。

推荐：

```text
API enqueue
   ↓
SQLite durable queue
   ↓
Worker claim + lease
   ↓
heartbeat
   ↓
Post Pipeline
   ↓
retry / resume / parent reconciliation
```

当前 V0.x 针对单机运行优化：SQLite WAL、busy timeout、共享限速、Worker lease、指数退避和 Raw API Snapshot 已实现。

当进入多机 Worker、多租户或高并发写入阶段，再迁移到 Postgres + Object Storage；上层 API、PlatformAdapter 和 Dataset Schema 尽量保持不变。


## Stage-level durable execution

生产队列现在按阶段执行：

```text
CREATOR_PIPELINE
└── POST_PIPELINE
    ├── POST_DETAIL
    ├── COMMENTS
    ├── MEDIA_DOWNLOAD
    ├── OCR
    ├── STT
    ├── VALIDATION
    └── EXPORT
```

查看任务树：

```text
GET /api/jobs/{job_id}/tree
```

定点修复失败阶段：

```text
POST /api/jobs/{job_id}/repair
```

Repair 只重开目标 Stage 及其下游依赖，不会重复执行已经完成且无依赖关系的阶段。


## 长期运行进程

生产建议运行三个独立进程：

```text
API
├── 接收导入/入队/查询请求
│
Worker(s)
├── Claim durable Stage Jobs
├── Lease / Heartbeat
├── Retry / Repair
│
Scheduler
└── 按 refresh_schedules 周期创建 CREATOR_REFRESH
```

启动：

```bash
uvicorn app.main:app
creator-dataset-worker
creator-dataset-scheduler
```

增量刷新：

```text
POST /api/creators/{creator_id}/enqueue-refresh
PUT  /api/creators/{creator_id}/refresh-schedule
GET  /api/creators/{creator_id}/refresh-history
GET  /api/creators/{creator_id}/changes
```

Refresh 会区分：

```text
content_changed
media_changed
engagement_changed
comments_changed
```

并只 fan-out 需要的 Stage Jobs。评论变化会主动失效旧评论 checkpoint；媒体变化会通过 `is_active` 对当前媒体版本进行 reconciliation。


## Local / Cloud 部署

当前明确支持：

```text
Local:
SQLite + Local Object Store

Cloud single-node:
SQLite + S3-compatible Object Store
```

本地 Docker：

```bash
cp .env.example .env
docker compose -f deploy/local/docker-compose.yml up -d --build
```

云端单节点：

```text
deploy/cloud-single-node/docker-compose.yml
```

对象存储支持本地和 S3-compatible backend。OCR/STT 会通过 storage abstraction 自动 materialize 文件，因此云端 Worker 不要求共享媒体磁盘。

部署自检：

```text
GET /api/system/capabilities
GET /api/system/readiness
GET /api/system/readiness?deep_storage=true
```

数据库升级已经使用 `schema_migrations` 记录版本。

安全备份：

```bash
creator-dataset-backup --output backups
```

当前 **不支持多主机 Worker + SQLite**。真正的多节点云部署将在 Postgres Repository 完成后开放。
