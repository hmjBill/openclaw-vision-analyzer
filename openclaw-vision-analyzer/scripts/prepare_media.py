#!/usr/bin/env python3
"""Prepare local image/video for OpenAI-compatible multimodal requests."""

from __future__ import annotations

import argparse
import base64
import math
import json
import mimetypes
import pathlib
import shutil
import subprocess
import sys
from dataclasses import dataclass

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


BYTES_PER_MB = 1024 * 1024
DEFAULT_IMAGE_MAX_MB = 7
DEFAULT_VIDEO_MAX_MB = 7
DEFAULT_MAX_DIMENSION = 4096
DEFAULT_COMPAT_MAX_DIMENSION = 8192
DEFAULT_MAX_FRAMES = 8000
DEFAULT_MIN_FRAMES = 4
DEFAULT_FPS = 2.0
DEFAULT_MAX_REQUEST_MB = 10
LOW_RES_IMAGE_FORMATS = {"BMP", "JPEG", "PNG", "TIFF", "WEBP", "HEIC"}
HIGH_RES_IMAGE_FORMATS = {"JPEG", "PNG"}
VIDEO_MIME_WHITELIST = {
    "video/mp4",
    "video/x-msvideo",
    "video/x-matroska",
    "video/quicktime",
    "video/x-flv",
    "video/x-ms-wmv",
}
VIDEO_EXT_WHITELIST = {".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv"}


@dataclass(frozen=True)
class FileInfo:
    path: pathlib.Path
    size_bytes: int
    mime_type: str


def to_file_info(path: pathlib.Path) -> FileInfo:
    stat = path.stat()
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileInfo(path=path, size_bytes=stat.st_size, mime_type=mime_type)


def encode_data_url(path: pathlib.Path, mime_type: str) -> str:
    raw = path.read_bytes()
    encoded = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def estimate_data_url_bytes(raw_size_bytes: int, mime_type: str) -> int:
    b64_chars = 4 * math.ceil(raw_size_bytes / 3)
    prefix_len = len(f"data:{mime_type};base64,")
    return prefix_len + b64_chars


def normalize_image_format(image_format: str) -> str:
    normalized = (image_format or "").upper()
    alias = {"JPG": "JPEG", "TIF": "TIFF"}
    return alias.get(normalized, normalized)


def check_image(
    path: pathlib.Path,
    max_size_mb: int,
    max_dimension: int,
    compat_max_dimension: int,
    max_request_mb: int,
    emit_data_url: bool,
) -> dict:
    if Image is None:
        raise RuntimeError("Missing dependency: Pillow. Install with `python -m pip install pillow`.")

    info = to_file_info(path)
    with Image.open(path) as img:
        width, height = img.size
        image_format = normalize_image_format(img.format or "")

    size_ok = info.size_bytes <= max_size_mb * BYTES_PER_MB
    longest_edge = max(width, height)
    resolution_ok = longest_edge <= max_dimension
    within_compat_resolution = longest_edge <= compat_max_dimension
    if longest_edge <= DEFAULT_MAX_DIMENSION:
        allowed_formats = sorted(LOW_RES_IMAGE_FORMATS)
    elif longest_edge <= compat_max_dimension:
        allowed_formats = sorted(HIGH_RES_IMAGE_FORMATS)
    else:
        allowed_formats = []
    format_ok = image_format in set(allowed_formats)
    estimated_data_url_bytes = estimate_data_url_bytes(info.size_bytes, info.mime_type)
    request_body_ok = estimated_data_url_bytes <= max_request_mb * BYTES_PER_MB

    result = {
        "kind": "image",
        "path": str(path),
        "size_bytes": info.size_bytes,
        "mime_type": info.mime_type,
        "format": image_format,
        "width": width,
        "height": height,
        "checks": {
            "size_ok": size_ok,
            "resolution_ok": resolution_ok,
            "within_compat_resolution": within_compat_resolution,
            "format_ok": format_ok,
            "request_body_ok_for_base64": request_body_ok,
            "max_size_mb": max_size_mb,
            "max_dimension": max_dimension,
            "compat_max_dimension": compat_max_dimension,
            "max_request_mb": max_request_mb,
            "allowed_formats_for_current_resolution": allowed_formats,
        },
        "estimated_data_url_bytes": estimated_data_url_bytes,
        "strategy": (
            "direct_base64"
            if size_ok and resolution_ok and format_ok and request_body_ok
            else "reject"
        ),
    }
    if emit_data_url and result["strategy"] == "direct_base64":
        result["data_url"] = encode_data_url(path, info.mime_type)
    return result


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg"):
        return
    raise RuntimeError("Missing dependency: ffmpeg. Install ffmpeg and ensure it is available in PATH.")


def extract_frames(
    input_path: pathlib.Path,
    frames_dir: pathlib.Path,
    fps: float,
    max_frames: int,
) -> list[pathlib.Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = frames_dir / "frame_%06d.jpg"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        f"fps={fps}",
        "-q:v",
        "2",
        str(output_pattern),
    ]
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {completed.stderr.strip()}")

    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if len(frames) > max_frames:
        extras = frames[max_frames:]
        for frame in extras:
            frame.unlink(missing_ok=True)
        frames = frames[:max_frames]
    return frames


def check_video(
    path: pathlib.Path,
    max_size_mb: int,
    frames_dir: pathlib.Path,
    fps: float,
    min_frames: int,
    max_frames: int,
    max_request_mb: int,
    emit_data_url: bool,
) -> dict:
    info = to_file_info(path)
    ext = path.suffix.lower()
    format_ok = ext in VIDEO_EXT_WHITELIST or info.mime_type in VIDEO_MIME_WHITELIST
    size_ok = info.size_bytes <= max_size_mb * BYTES_PER_MB
    estimated_data_url_bytes = estimate_data_url_bytes(info.size_bytes, info.mime_type)
    request_body_ok = estimated_data_url_bytes <= max_request_mb * BYTES_PER_MB

    result = {
        "kind": "video",
        "path": str(path),
        "size_bytes": info.size_bytes,
        "mime_type": info.mime_type,
        "checks": {
            "size_ok_for_base64": size_ok,
            "format_ok": format_ok,
            "request_body_ok_for_base64": request_body_ok,
            "max_size_mb": max_size_mb,
            "max_request_mb": max_request_mb,
            "fps": fps,
            "min_frames": min_frames,
            "max_frames": max_frames,
            "allowed_extensions": sorted(VIDEO_EXT_WHITELIST),
        },
        "estimated_data_url_bytes": estimated_data_url_bytes,
    }

    if not format_ok:
        result["strategy"] = "reject"
        return result

    if size_ok and request_body_ok:
        result["strategy"] = "direct_base64"
        if emit_data_url:
            result["data_url"] = encode_data_url(path, info.mime_type)
        return result

    ensure_ffmpeg()
    frames = extract_frames(path, frames_dir, fps=fps, max_frames=max_frames)
    result["strategy"] = "frame_extraction"
    result["frame_count"] = len(frames)
    result["checks"]["min_frames_met"] = len(frames) >= min_frames
    result["frames"] = [str(f) for f in frames]
    if len(frames) < min_frames:
        result["strategy"] = "reject"
        result["error"] = f"extracted frames ({len(frames)}) below minimum required ({min_frames})"
        return result
    if emit_data_url:
        result["frame_data_urls"] = [encode_data_url(f, "image/jpeg") for f in frames]
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare local media for vision model input.")
    sub = parser.add_subparsers(dest="kind", required=True)

    image = sub.add_parser("image", help="Validate and optionally encode an image.")
    image.add_argument("--path", required=True, help="Absolute or relative image path.")
    image.add_argument("--max-size-mb", type=int, default=DEFAULT_IMAGE_MAX_MB)
    image.add_argument("--max-dimension", type=int, default=DEFAULT_MAX_DIMENSION)
    image.add_argument("--compat-max-dimension", type=int, default=DEFAULT_COMPAT_MAX_DIMENSION)
    image.add_argument("--max-request-mb", type=int, default=DEFAULT_MAX_REQUEST_MB)
    image.add_argument("--emit-data-url", action="store_true")

    video = sub.add_parser("video", help="Validate and prepare a video.")
    video.add_argument("--path", required=True, help="Absolute or relative video path.")
    video.add_argument("--max-size-mb", type=int, default=DEFAULT_VIDEO_MAX_MB)
    video.add_argument("--fps", type=float, default=DEFAULT_FPS)
    video.add_argument("--min-frames", type=int, default=DEFAULT_MIN_FRAMES)
    video.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
    video.add_argument("--max-request-mb", type=int, default=DEFAULT_MAX_REQUEST_MB)
    video.add_argument("--frames-dir", default="tmp_frames")
    video.add_argument("--emit-data-url", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    path = pathlib.Path(args.path).expanduser().resolve()
    if not path.exists():
        print(json.dumps({"error": f"path not found: {path}"}, ensure_ascii=False), file=sys.stderr)
        return 1

    try:
        if args.kind == "image":
            payload = check_image(
                path=path,
                max_size_mb=args.max_size_mb,
                max_dimension=args.max_dimension,
                compat_max_dimension=args.compat_max_dimension,
                max_request_mb=args.max_request_mb,
                emit_data_url=args.emit_data_url,
            )
        else:
            frames_dir = pathlib.Path(args.frames_dir).expanduser().resolve()
            payload = check_video(
                path=path,
                max_size_mb=args.max_size_mb,
                frames_dir=frames_dir,
                fps=args.fps,
                min_frames=args.min_frames,
                max_frames=args.max_frames,
                max_request_mb=args.max_request_mb,
                emit_data_url=args.emit_data_url,
            )
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
