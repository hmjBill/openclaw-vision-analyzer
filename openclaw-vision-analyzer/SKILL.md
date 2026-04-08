---
name: openclaw-vision-analyzer
description: 为 Openclaw 提供图片与视频识别能力。用于分析图片内容、提取图中文字或界面元素、对比多张图片、理解视频内容、从视频中提取关键信息。触发场景包括用户上传本地图片/视频、提供公网媒体 URL、要求识别截图/图表/架构图、或要求分析视频画面与字幕信息。
---

# Openclaw Vision Analyzer

## 执行流程

1. 视觉请求识别。
- 当输入包含图片、截图、图表、架构图、视频文件、视频 URL 或要求识别视觉内容时触发。

2. 模型路由。
- 当前模型支持视觉时，直接执行。
- 当前模型不支持视觉时，路由到 `qwen3.5-plus` 或 `kimi-k2.5` 执行视觉理解，再返回结果。

3. 媒体输入分流。
- 支持本地路径与公网 URL。
- 本地输入按文件大小、分辨率、格式、Base64 请求体估算进行分流。
- 公网 URL 输入在调用前校验响应头约束。

4. 接口一致性。
- API Key 与 Base URL 使用 Openclaw 现有配置。
- 不新增环境变量要求。

## 输入与限制规则

1. 图片输入。
- 本地文件大小：`<= 7MB`（按 Base64 请求体上限约束，默认总请求体 `<= 10MB`）。
- 默认分辨率上限：`<= 4096`（4K）。
- 4K 以下格式：`BMP/JPEG/PNG/TIFF/WEBP/HEIC`。
- 4K-8K 兼容格式：`JPEG/PNG`（仅在显式放宽分辨率时启用）。

2. 视频输入。
- 支持格式：`MP4/AVI/MKV/MOV/FLV/WMV`。
- 本地视频 `<= 7MB` 且 Base64 请求体估算 `<= 10MB`：`direct_base64`。
- 本地视频超阈值：`frame_extraction`（按多图请求）。
- 公网 `video_url`：远端响应需包含 `Content-Length` 与 `Content-Type`。
- `qwen3.5/Qwen3-VL` 的公网 URL 模式可到 `2GB`（以服务端能力为准）。

3. 抽帧约束。
- 默认抽帧速率：`2 fps`，可按任务密度调整。
- `qwen3.5` 系列帧数范围：`4~8000`。
- 超过上限时截断至上限；低于最小帧数时返回限制命中信息。

4. Token 预算。
- 视频抽帧模式需控制“全部帧 + 文本”总 Token 不超过模型上限。

## 消息构造规范

1. 单图分析（`image_url`）。

```json
{
  "role": "user",
  "content": [
    {
      "type": "image_url",
      "image_url": { "url": "https://example.com/a.png" }
    },
    { "type": "text", "text": "描述这张图的重点信息" }
  ]
}
```

2. 多图对比（多个 `image_url`）。

```json
{
  "role": "user",
  "content": [
    { "type": "image_url", "image_url": { "url": "https://example.com/a.png" } },
    { "type": "image_url", "image_url": { "url": "https://example.com/b.png" } },
    { "type": "text", "text": "比较两张图的主要差异" }
  ]
}
```

3. 视频直接 URL（`video_url`）。

```json
{
  "role": "user",
  "content": [
    { "type": "video_url", "video_url": { "url": "https://example.com/video.mp4" } },
    { "type": "text", "text": "总结视频中的关键事件" }
  ]
}
```

4. 视频抽帧后多图输入（帧转 `image_url`）。

```json
{
  "role": "user",
  "content": [
    { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } },
    { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } },
    { "type": "text", "text": "根据这些帧描述视频内容" }
  ]
}
```

## 脚本资源

1. 使用 `scripts/prepare_media.py` 预处理本地媒体文件。
- 图片模式：检查大小、分辨率、分辨率对应格式、Base64 请求体估算，必要时输出 Data URL。
- 视频模式：检查格式与大小，按规则执行直传或抽帧，并输出结构化结果。

2. 常用命令。

```bash
python scripts/prepare_media.py image --path /abs/path/image.png
python scripts/prepare_media.py image --path /abs/path/image.png --emit-data-url
python scripts/prepare_media.py video --path /abs/path/video.mp4 --frames-dir ./tmp_frames --fps 2 --min-frames 4 --max-frames 8000
python scripts/prepare_media.py video --path /abs/path/video.mp4 --emit-data-url
```

3. 读取补充参考。
- 规则与示例：`references/constraints-and-examples.md`

## 返回行为

1. 返回模型原始分析结果。
2. 返回输入处理路径（直传 URL、Base64、或抽帧）。
3. 在命中限制时返回限制项与触发条件（大小/分辨率/格式/请求体/帧数/Token 预算）。
4. 批量场景可使用异步调用（`AsyncOpenAI`）并返回逐任务结果。
