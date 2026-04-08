# openclaw-vision-analyzer

`openclaw-vision-analyzer` 是一个为 Openclaw 提供图片与视频识别处理流程的 skill 项目。仓库包含技能说明、媒体预处理脚本和约束参考文档。

## 项目范围

- 识别图片与视频相关请求。
- 在当前模型不支持视觉输入时，切换到视觉模型执行识别。
- 按输入大小、分辨率和格式规则选择处理路径。
- 返回结构化处理结果与限制命中信息。

## 处理路径

- 图片输入：
  - 来源支持本地路径或公网 URL。
  - 默认本地限制：文件大小 `<= 7MB`，最大边 `<= 4096`。
  - 分辨率格式规则：4K 以下支持 `BMP/JPEG/PNG/TIFF/WEBP/HEIC`，4K-8K 仅 `JPEG/PNG`（显式放宽时）。
  - 默认策略：符合限制且 Base64 请求体估算 `<= 10MB` 走 `direct_base64`，否则 `reject`。
- 视频输入：
  - 来源支持本地路径或公网 URL。
  - 支持格式：`MP4/AVI/MKV/MOV/FLV/WMV`。
  - 默认本地阈值：`<= 7MB` 且 Base64 请求体估算 `<= 10MB` 走 `direct_base64`。
  - 其他情况走 `frame_extraction`，帧数范围默认 `4~8000`。

## 仓库结构

- `openclaw-vision-analyzer/SKILL.md`：技能触发、约束、消息构造与返回行为说明。
- `openclaw-vision-analyzer/agents/openai.yaml`：技能展示信息与默认提示词。
- `openclaw-vision-analyzer/scripts/prepare_media.py`：本地媒体校验、转 Data URL、视频抽帧脚本。
- `openclaw-vision-analyzer/references/constraints-and-examples.md`：约束与示例参考。
- `openclaw-vision-analyzer/references/doc-final-summary.md`：实现文档收束归纳。
- `openclaw-vision-analyzer/references/pdf-implementation-sync.md`：PDF 具体实现与仓库落地映射。

## 运行脚本

```bash
python openclaw-vision-analyzer/scripts/prepare_media.py --help
python openclaw-vision-analyzer/scripts/prepare_media.py image --path /abs/path/image.png
python openclaw-vision-analyzer/scripts/prepare_media.py video --path /abs/path/video.mp4 --frames-dir ./tmp_frames --fps 2 --min-frames 4 --max-frames 8000
```

## 依赖

- Python 3
- `Pillow`（图片分辨率与格式读取）
- `ffmpeg`（超限视频抽帧）
