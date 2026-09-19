# Product Requirements Document (PRD)

## 1. 产品定义

Creator Dataset 将公开 Creator 内容转换为结构化、可恢复、可审计、可供后续 AI 使用的数据集。

V0.1 只聚焦一个问题：

> 输入一个小红书 Creator 主页 URL，稳定生成该 Creator 的公开内容 Dataset。

## 2. V0.1 用户流程

1. 用户提交 Creator 主页 URL。
2. 系统识别平台、Creator ID 与基础资料。
3. 系统枚举该 Creator 的全部可发现公开笔记。
4. 对每篇笔记独立执行采集任务：
   - 标题
   - 正文
   - 发布时间
   - 来源 URL
   - 图片
   - 视频
   - 点赞 / 收藏 / 分享 / 评论数（若平台可见）
   - 一级评论
   - 二级回复
   - 评论图片
5. 系统持续记录任务进度和失败原因。
6. 系统执行完整性审计。
7. 用户可导出 SQLite、JSONL、Markdown 和媒体文件。

## 3. 核心成功标准

### 3.1 Creator Discovery

- 能从主页 URL 解析 Creator。
- 能分页发现全部当前可访问的公开笔记。
- 支持重复执行而不重复创建数据。

### 3.2 Post Capture

每篇 Post 至少保存：

- platform
- creator_id
- post_id
- source_url
- title
- content
- post_type
- published_at
- metrics
- raw_json

### 3.3 Media Capture

支持：

- 原图
- 视频
- Cover
- 评论图片

每个媒体资源有独立下载状态，并支持重试。

### 3.4 Comment Capture

必须保存：

- 一级评论
- 全部可获取二级回复
- comment_id
- root_comment_id
- parent_comment_id
- 用户信息
- 文本
- 点赞数
- 发布时间
- IP 属地（平台公开提供时）
- 评论图片
- raw_json

### 3.5 Completeness Audit

禁止仅因为 API 返回 has_more=false 就直接显示“100% 完成”。

至少记录：

- 平台报告评论数
- 实际唯一评论数
- 一级评论数
- 回复数
- 一级分页是否耗尽
- 所有回复线程是否耗尽
- 失败线程数
- completeness_ratio
- 差异说明

## 4. 状态模型

Job 状态：

- PENDING
- RUNNING
- COMPLETE
- PARTIAL
- BLOCKED
- FAILED

其中：

- COMPLETE：当前可访问分页已完整耗尽，并通过审计。
- PARTIAL：获得部分数据，但存在缺页、缺评论、失败线程或数量差异。
- BLOCKED：因登录失效、验证码、风控、限流等无法继续。
- FAILED：非可恢复或超过重试阈值。

## 5. 非功能需求

### 可恢复

任何 Creator 采集任务中断后，可以从未完成单元继续，不重复下载已完成内容。

### 幂等

同一 Creator / Post / Comment 重复抓取不会创建重复数据。

### 可追溯

标准化字段应能追溯到 raw response。

### 可扩展

核心系统不得硬编码为小红书专用；必须通过 PlatformAdapter 接入平台。

## 6. V0.1 不做

- 微信公众号 Adapter
- 抖音 / B站 / 知乎 Adapter
- Embedding
- 向量数据库
- RAG
- AI Chat
- 自动知识图谱
- 小程序
- SaaS 多租户
- 计费

## 7. 后续方向

V0.2：
- 微信公众号 Adapter
- 公众号历史文章与评论
- 多平台统一 Dataset Schema

V0.3：
- OCR
- 视频 STT
- 内容标准化 Markdown
- 统一 Export Pipeline

V1：
- Creator Knowledge Layer
- FAQ
- Topics
- Pain Points
- Product Signals
- RAG / Search / AI Q&A
