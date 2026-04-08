# PDF 实现同步说明

## 1. 同步来源
- 源文档：`两句话，让Openclaw具有图片和视频识别能力.pdf`
- 同步目标：将 PDF 中“图片/视频识别实现流程、限制规则、消息结构、并发方式”落到仓库文档。

## 2. 能力与路由
- 视觉模型：`qwen3.5-plus`、`kimi-k2.5`。
- 非视觉模型场景：先调用视觉模型完成识别，再返回主流程。
- 本仓库对应位置：
  - `SKILL.md` 的“模型路由”与“执行流程”章节。
  - `references/constraints-and-examples.md` 的“模型能力路由”表。

## 3. 图片实现规则
- 本地图片大小阈值：`<= 7MB`。
- 默认分辨率阈值：最大边 `<= 4096`。
- 分辨率格式联动：
  - 4K 以下：`BMP/JPEG/PNG/TIFF/WEBP/HEIC`
  - 4K-8K：`JPEG/PNG`
- OpenAI 兼容输入：`content` 中使用 `image_url`（可为公网 URL 或 Data URL）。
- 本仓库对应位置：
  - `SKILL.md` 的“图片输入”与“消息构造规范”。
  - `scripts/prepare_media.py` 的 `check_image`。

## 4. 视频实现规则
- 支持格式：`MP4/AVI/MKV/MOV/FLV/WMV`。
- 本地视频分流：
  - `<= 7MB` 且 Base64 请求体估算 `<= 10MB`：`direct_base64`
  - 其他：`frame_extraction`
- 公网 `video_url` 约束：
  - 远端响应头需包含 `Content-Length` 和 `Content-Type`
  - `qwen3.5/Qwen3-VL` URL 模式上限可到 `2GB`（服务端能力边界）
- 抽帧范围：`4~8000` 帧。
- OpenAI 兼容输入：`content` 中使用 `video_url`，或抽帧后多个 `image_url`。
- 本仓库对应位置：
  - `SKILL.md` 的“视频输入”“抽帧约束”“消息构造规范”。
  - `scripts/prepare_media.py` 的 `check_video` 与 `extract_frames`。

## 5. 并发与接口约束
- 高并发场景：使用 `AsyncOpenAI` 异步调用。
- API Key 与 Base URL：保持 Openclaw 现有配置，不新增环境变量要求。
- 本仓库对应位置：
  - `SKILL.md` 的“返回行为”与“接口一致性”。
  - `references/doc-final-summary.md` 的并发与接口章节。

## 6. 可执行映射（脚本命令）
```bash
python scripts/prepare_media.py image --path /abs/path/image.png
python scripts/prepare_media.py image --path /abs/path/image.png --emit-data-url
python scripts/prepare_media.py video --path /abs/path/video.mp4 --frames-dir ./tmp_frames --fps 2 --min-frames 4 --max-frames 8000
python scripts/prepare_media.py video --path /abs/path/video.mp4 --emit-data-url
```

## 7. 规则冲突处理记录
- PDF 中抽帧频率同时出现 `2 fps` 与 `10 fps` 两种描述。
- 仓库当前基线采用 `2 fps`，并通过命令参数 `--fps` 支持调整到其他值。
