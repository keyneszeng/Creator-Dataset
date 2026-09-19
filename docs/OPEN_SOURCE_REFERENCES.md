# Open Source References

> 本文件记录可研究/复用的开源项目方向。引入任何代码前必须单独核实其 LICENSE，并遵守许可证要求。

## 1. xiaohongshu-cli

Repository:

https://github.com/jackwener/xiaohongshu-cli

重点研究：

- Creator / user API
- user posts
- comments pagination
- sub-comments
- Cookie / QR auth
- xsec_token handling
- retry / cooldown
- CLI → Python API 的封装方式

建议用途：

> V0.1 小红书 Adapter 的主要参考之一。

不要直接将整个 CLI 与业务核心绑定，应将平台请求能力封装到 XiaohongshuAdapter。

## 2. MediaCrawler

Repository:

https://github.com/NanmiCoder/MediaCrawler

重点研究：

- creator mode
- comment pagination
- sub-comment pagination
- cursor / has_more 处理
- storage abstraction
- 多平台 Adapter 思路

建议用途：

> 重点参考评论线程枚举与多平台抽象，不建议直接把整个项目作为 Creator Dataset 核心。

## 3. hammershock/xhs-cli

Repository:

https://github.com/hammershock/xhs-cli

重点研究：

- content.md
- meta.json
- images/
- video
- comments.json
- comment_images
- OCR / STT export flow

建议用途：

> 参考单篇 Post 的落盘结构与 enrichment pipeline。

## 4. wechatDownload

Repository:

https://github.com/qiye45/wechatDownload

未来 V0.2 重点研究：

- 公众号历史文章 discovery
- 批量下载
- Markdown / PDF / DOCX export
- 图片 / 视频 / 音频
- 评论
- 评论图片

建议用途：

> WechatAdapter 的主要参考项目之一。

## 5. EasyWechatDownload

Repository:

https://github.com/yangbuyiya/EasyWechatDownload

重点研究：

- 搜索公众号
- 历史文章 UI
- 批量下载任务
- GUI 任务反馈
- 评论相关处理

建议用途：

> 参考公众号 discovery 用户流程与桌面端任务体验。

## 6. Reuse Policy

引入第三方代码前必须执行：

1. 核对 LICENSE。
2. 确认是否允许商业使用、修改、再分发。
3. 保留必要版权声明。
4. 对 GPL/AGPL 等强 copyleft 许可证单独评估。
5. 尽量通过 adapter / subprocess / service boundary 降低许可证耦合。
6. 不复制未明确授权的代码片段。

## 7. Build vs Reuse

### 优先复用 / 参考

- Auth
- 平台 API 请求
- cursor pagination
- URL parsing
- media URL extraction
- comment parsing

### 必须自己掌控

- Unified Schema
- Job Engine
- Retry State
- Raw Archive
- Completeness Audit
- Export Contract
- Cross-platform Adapter Interface
- Dataset versioning

这些部分才是 Creator Dataset 的长期核心资产。
