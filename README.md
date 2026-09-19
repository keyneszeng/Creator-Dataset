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

pip install -e ".[dev,xhs]"

uvicorn app.main:app --reload
```

服务启动后：

```text
GET  /api/health
POST /api/creators/resolve
POST /api/creators/import
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

## V0.1 技术建议

- Python 3.12
- FastAPI
- SQLite
- asyncio queue（早期）/ Redis + RQ、Dramatiq 或 Celery（规模化后）
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
