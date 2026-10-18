#!/usr/bin/env python3
"""Generate one image through PackyAPI and save it atomically."""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import struct
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://www.packyapi.com/v1"
DEFAULT_MODEL = "gpt-image-2.5-flare"
VALID_QUALITY = ("low", "medium", "high", "auto")
VALID_FORMAT = ("png", "jpeg")


class ImagegenError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one image through PackyAPI."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt")
    source.add_argument("--prompt-file", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--quality", choices=VALID_QUALITY, default="medium")
    parser.add_argument("--output-format", choices=VALID_FORMAT, default="png")
    parser.add_argument("--moderation", choices=("auto", "low"), default="auto")
    parser.add_argument("--base-url", default=os.getenv("PACKY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt is not None:
        prompt = args.prompt
    else:
        try:
            prompt = args.prompt_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ImagegenError(f"Cannot read prompt file: {exc}") from exc
    prompt = prompt.strip()
    if not prompt:
        raise ImagegenError("Prompt must not be empty.")
    return prompt


def validate_size(value: str) -> None:
    if value == "auto":
        return
    try:
        width, height = (int(part) for part in value.lower().split("x", 1))
    except (TypeError, ValueError) as exc:
        raise ImagegenError("Size must be 'auto' or WIDTHxHEIGHT.") from exc
    pixels = width * height
    if width <= 0 or height <= 0 or width % 16 or height % 16:
        raise ImagegenError("Image width and height must be positive multiples of 16.")
    if max(width, height) > 3840:
        raise ImagegenError("Maximum image edge is 3840 pixels.")
    if max(width, height) / min(width, height) > 3:
        raise ImagegenError("Long-to-short edge ratio must not exceed 3:1.")
    if not 655_360 <= pixels <= 8_294_400:
        raise ImagegenError("Total pixels must be between 655,360 and 8,294,400.")


def api_key() -> str:
    key = os.getenv("PACKY_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ImagegenError(
            "PACKY_API_KEY is not set. Export a PackyAPI Sora-group token locally."
        )
    return key


def error_message(body: bytes, status: int) -> str:
    try:
        payload = json.loads(body.decode("utf-8"))
        error = payload.get("error", payload)
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message") or error.get("type")
            detail = ": ".join(str(value) for value in (code, message) if value)
            return f"PackyAPI HTTP {status}: {detail or 'request failed'}"
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    return f"PackyAPI HTTP {status}: request failed"


def request_json(url: str, payload: dict[str, Any], key: str, timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise ImagegenError(error_message(exc.read(), exc.code)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ImagegenError(f"PackyAPI request failed: {exc.reason if hasattr(exc, 'reason') else exc}") from exc
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImagegenError("PackyAPI returned a non-JSON response.") from exc
    if not isinstance(result, dict):
        raise ImagegenError("PackyAPI returned an unexpected response shape.")
    return result


def download(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "image/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            return response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise ImagegenError(f"Image download failed: {exc}") from exc


def extract_image(result: dict[str, Any], timeout: int) -> tuple[bytes, str | None]:
    data = result.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        if "error" in result:
            raise ImagegenError(error_message(json.dumps(result).encode(), 200))
        raise ImagegenError("PackyAPI response contains no image data.")
    item = data[0]
    revised_prompt = item.get("revised_prompt")
    if isinstance(item.get("b64_json"), str):
        try:
            return base64.b64decode(item["b64_json"], validate=True), revised_prompt
        except (ValueError, base64.binascii.Error) as exc:
            raise ImagegenError("PackyAPI returned invalid Base64 image data.") from exc
    if isinstance(item.get("url"), str):
        return download(item["url"], timeout), revised_prompt
    raise ImagegenError("PackyAPI returned neither b64_json nor an image URL.")


def validate_image(raw: bytes, output_format: str) -> tuple[int | None, int | None]:
    if output_format == "png":
        if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n":
            raise ImagegenError("Downloaded data is not a valid PNG file.")
        return struct.unpack(">II", raw[16:24])
    if len(raw) < 4 or raw[:2] != b"\xff\xd8" or raw[-2:] != b"\xff\xd9":
        raise ImagegenError("Downloaded data is not a valid JPEG file.")
    return None, None


def write_atomic(path: Path, raw: bytes, force: bool) -> None:
    if path.exists() and not force:
        raise ImagegenError(f"Output already exists: {path} (use --force to replace it)")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            temp_name = handle.name
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    args = parse_args()
    try:
        prompt = read_prompt(args)
        validate_size(args.size)
        expected_suffix = ".jpg" if args.output_format == "jpeg" else ".png"
        if args.out.suffix.lower() not in ({".jpg", ".jpeg"} if args.output_format == "jpeg" else {".png"}):
            raise ImagegenError(f"Output path must use the {expected_suffix} extension.")
        payload = {
            "model": args.model,
            "prompt": prompt,
            "n": 1,
            "size": args.size,
            "quality": args.quality,
            "output_format": args.output_format,
            "moderation": args.moderation,
        }
        if args.dry_run:
            print(json.dumps({"endpoint": f"{args.base_url.rstrip('/')}/images/generations", "out": str(args.out), **payload}, ensure_ascii=False, indent=2))
            return 0
        print(f"Calling PackyAPI {args.model}; this may take several minutes.", file=sys.stderr)
        result = request_json(
            f"{args.base_url.rstrip('/')}/images/generations",
            payload,
            api_key(),
            args.timeout,
        )
        raw, revised_prompt = extract_image(result, args.timeout)
        width, height = validate_image(raw, args.output_format)
        write_atomic(args.out, raw, args.force)
        dimensions = f" ({width}x{height})" if width and height else ""
        print(f"Wrote {args.out.resolve()}{dimensions}")
        if revised_prompt:
            print(f"Revised prompt: {revised_prompt}")
        return 0
    except ImagegenError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
