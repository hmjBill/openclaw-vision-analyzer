---
name: openclaw-vision-analyzer
description: 为 Openclaw 提供图片与视频识别能力。用于分析图片内容、提取图中文字或界面元素、对比多张图片、理解视频内容、从视频中提取关键信息。触发场景包括用户上传本地图片/视频、提供公网媒体 URL、要求识别截图/图表/架构图、或要求分析视频画面与字幕信息。
---

# Openclaw Vision Analyzer

## 执行流程

1. 判断请求是否涉及视觉输入。
- 识别图片、截图、图表、架构图、视频分析等请求。

2. 选择视觉模型。
- 若当前模型不支持视觉输入，切换到 `qwen3.5-plus` 或 `kimi-k2.5` 执行视觉理解。
- 视觉结果返回后，再继续当前对话流程。

3. 处理图片输入。
- 支持来源：本地文件路径或公网 URL。
- 本地图片默认限制：文件大小 `<= 7MB`，分辨率 `<= 4096`（4K）。
- 本地图片超限时，终止调用并返回限制说明。

4. 处理视频输入。
- 支持来源：本地文件路径或公网 URL。
- 本地视频 `<= 7MB`：可直接转 Base64 进行请求。
- 本地视频 `> 7MB`：先抽帧，再按多图片方式请求。
- 抽帧上限：`<= 8000` 帧。

5. 并发调用策略。
- 批量图片对比或高并发问题，使用异步调用（`AsyncOpenAI`）处理多请求。

6. 保持接口配置一致。
- API Key 与 Base URL 保持 Openclaw 现有配置。
- 不新增环境变量配置要求。

## 输入与限制规则

1. 图片限制。
- 文件大小：`<= 7MB`。
- 分辨率：默认 `<= 4K`。
- 4K 以下支持格式：`BMP/JPEG/PNG/TIFF/WEBP/HEIC`。
- 4K-8K 兼容格式：`JPEG/PNG`（仅在明确允许 8K 时使用）。

2. 视频限制。
- 公网 URL：`qwen3.5/Qwen3-VL` 最高 `2GB`（需远端返回 `Content-Length` 和 `Content-Type`）。
- Base64：总请求体小于 `10MB`，本地文件按 `<= 7MB` 执行。
- 支持格式：`MP4/AVI/MKV/MOV/FLV/WMV`。

3. 帧数限制（视频抽帧模式）。
- `qwen3.5` 系列：`4~8000` 帧。
- 若超过上限，截断至上限后继续请求。

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
- 图片模式：检查大小、分辨率、格式，必要时输出 Data URL。
- 视频模式：按大小决定直传或抽帧，并输出结构化结果。

2. 常用命令。

```bash
python scripts/prepare_media.py image --path /abs/path/image.png
python scripts/prepare_media.py image --path /abs/path/image.png --emit-data-url
python scripts/prepare_media.py video --path /abs/path/video.mp4 --frames-dir ./tmp_frames
python scripts/prepare_media.py video --path /abs/path/video.mp4 --emit-data-url
```

3. 读取补充参考。
- 规则与示例：`references/constraints-and-examples.md`

## 返回行为

1. 返回模型原始分析结果。
2. 返回输入处理路径（直传 URL、Base64、或抽帧）。
3. 在命中限制时返回限制项与触发条件（大小/分辨率/格式/帧数）。
