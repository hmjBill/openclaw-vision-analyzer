# Openclaw Vision Constraints and Examples

## 1) 模型能力路由

| 模型 | 是否原生支持视觉 | 处理方式 |
|---|---|---|
| qwen3.5-plus | 是 | 直接接收图片/视频输入 |
| kimi-k2.5 | 是 | 直接接收图片/视频输入 |
| 其他文本模型 | 否 | 先路由到视觉模型再返回结果 |

## 2) 图片限制

- 本地图片大小：`<= 7MB`
- 默认分辨率：`<= 4K`（`4096`）
- 4K 以下支持：`BMP` `JPEG` `PNG` `TIFF` `WEBP` `HEIC`
- 4K-8K 兼容：`JPEG` `PNG`（仅在显式允许 8K 时使用）

## 3) 视频限制

- 支持格式：`MP4` `AVI` `MKV` `MOV` `FLV` `WMV`
- 本地 `<= 7MB` 且 Base64 请求体估算 `<= 10MB`：可直接 Base64 调用
- 本地 `> 7MB`：抽帧后按多图调用
- 公网 URL：服务端响应必须包含 `Content-Length` 与 `Content-Type`
- 直接视频 URL（qwen3.5/Qwen3-VL）可支持到 `2GB`

## 4) 抽帧规则

- 抽帧上限：`8000` 帧（qwen3.5 系列）
- 抽帧下限：`4` 帧（qwen3.5 系列）
- 默认抽帧速率：`2 fps`
- 支持通过参数调整 `fps`，用于适配更高密度采样

## 5) Token 预算规则

- 视频抽帧模式中，“所有帧 + 文本”的总 Token 必须不超过模型上限。
- 若估算超限，应降低 `fps`、减少帧数或缩短文本提示。

## 6) OpenAI 兼容请求片段

### 单图

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        { "type": "image_url", "image_url": { "url": "https://example.com/a.png" } },
        { "type": "text", "text": "识别图片中的文字和结构" }
      ]
    }
  ]
}
```

### 多图

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        { "type": "image_url", "image_url": { "url": "https://example.com/1.png" } },
        { "type": "image_url", "image_url": { "url": "https://example.com/2.png" } },
        { "type": "text", "text": "比较两张图片的区别" }
      ]
    }
  ]
}
```

### 视频 URL

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        { "type": "video_url", "video_url": { "url": "https://example.com/video.mp4" } },
        { "type": "text", "text": "分析视频中的主要事件" }
      ]
    }
  ]
}
```

### 抽帧后多图

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } },
        { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } },
        { "type": "text", "text": "根据这些帧总结视频内容" }
      ]
    }
  ]
}
```
