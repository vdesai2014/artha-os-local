"""artha camera <topic> — save one frame from a camera topic via video_bridge."""

from __future__ import annotations

import io
import re
from pathlib import Path

import httpx

from cli.common import find_repo_root, video_bridge_url, die


def _sanitize(topic: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", topic)


def _read_one_jpeg(client: httpx.Client, url: str, timeout: float) -> bytes:
    """Pull one JPEG out of the MJPEG multipart stream, then close."""
    boundary = b"--frame"
    chunks: list[bytes] = []
    with client.stream("GET", url, timeout=timeout) as response:
        if response.status_code >= 400:
            raise RuntimeError(f"video_bridge returned {response.status_code}")
        buf = b""
        for chunk in response.iter_bytes():
            buf += chunk
            # Find the first complete part: --frame\r\n<headers>\r\n\r\n<jpeg>\r\n--frame
            start = buf.find(b"\r\n\r\n")
            if start < 0:
                continue
            after_headers = buf[start + 4:]
            end = after_headers.find(boundary)
            if end < 0:
                continue
            jpeg = after_headers[: end].rstrip(b"\r\n")
            return jpeg
        raise RuntimeError("stream closed before a complete frame arrived")


def run(args) -> int:
    find_repo_root()  # just assert we're inside the repo
    url = f"{video_bridge_url()}/{args.topic.lstrip('/')}"
    save_path = Path(args.save) if args.save else Path(f"/tmp/{_sanitize(args.topic)}.png")

    try:
        with httpx.Client() as client:
            jpeg = _read_one_jpeg(client, url, args.timeout)
    except httpx.RequestError as exc:
        die(f"video_bridge unreachable at {url}: {exc}")
    except Exception as exc:
        die(str(exc))

    # Decode JPEG → PNG via Pillow for a portable, no-assumed-viewer output.
    try:
        from PIL import Image
    except ImportError:
        die("Pillow is required for `artha camera` (pip install pillow)")
    img = Image.open(io.BytesIO(jpeg))
    save_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(save_path)
    print(f"saved {img.size[0]}x{img.size[1]} PNG to {save_path}")
    return 0
