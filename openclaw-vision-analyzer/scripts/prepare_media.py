#!/usr/bin/env python3
"""Prepare local image/video for OpenAI-compatible multimodal requests."""

from __future__ import annotations

import argparse
import base64
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
DEFAULT_MAX_FRAMES = 8000
DEFAULT_FPS = 2.0


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


def check_image(
    path: pathlib.Path,
    max_size_mb: int,
    max_dimension: int,
    emit_data_url: bool,
) -> dict:
    if Image is None:
        raise RuntimeError("Missing dependency: Pillow. Install with `python -m pip install pillow`.")

    info = to_file_info(path)
    with Image.open(path) as img:
        width, height = img.size
        image_format = (img.format or "").upper()

    size_ok = info.size_bytes <= max_size_mb * BYTES_PER_MB
    resolution_ok = max(width, height) <= max_dimension

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
            "max_size_mb": max_size_mb,
            "max_dimension": max_dimension,
        },
        "strategy": "direct_base64" if size_ok and resolution_ok else "reject",
    }
    if emit_data_url and size_ok and resolution_ok:
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
    max_frames: int,
    emit_data_url: bool,
) -> dict:
    info = to_file_info(path)
    size_ok = info.size_bytes <= max_size_mb * BYTES_PER_MB

    result = {
        "kind": "video",
        "path": str(path),
        "size_bytes": info.size_bytes,
        "mime_type": info.mime_type,
        "checks": {
            "size_ok_for_base64": size_ok,
            "max_size_mb": max_size_mb,
            "fps": fps,
            "max_frames": max_frames,
        },
    }

    if size_ok:
        result["strategy"] = "direct_base64"
        if emit_data_url:
            result["data_url"] = encode_data_url(path, info.mime_type)
        return result

    ensure_ffmpeg()
    frames = extract_frames(path, frames_dir, fps=fps, max_frames=max_frames)
    result["strategy"] = "frame_extraction"
    result["frame_count"] = len(frames)
    result["frames"] = [str(f) for f in frames]
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
    image.add_argument("--emit-data-url", action="store_true")

    video = sub.add_parser("video", help="Validate and prepare a video.")
    video.add_argument("--path", required=True, help="Absolute or relative video path.")
    video.add_argument("--max-size-mb", type=int, default=DEFAULT_VIDEO_MAX_MB)
    video.add_argument("--fps", type=float, default=DEFAULT_FPS)
    video.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
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
                emit_data_url=args.emit_data_url,
            )
        else:
            frames_dir = pathlib.Path(args.frames_dir).expanduser().resolve()
            payload = check_video(
                path=path,
                max_size_mb=args.max_size_mb,
                frames_dir=frames_dir,
                fps=args.fps,
                max_frames=args.max_frames,
                emit_data_url=args.emit_data_url,
            )
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
