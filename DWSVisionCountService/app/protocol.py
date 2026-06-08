"""DWS TCP byte 协议。

格式：
[4 bytes big-endian header_json_length][header_json utf-8][image bytes]
响应：
[4 bytes big-endian response_json_length][response_json utf-8]
"""

from __future__ import annotations

import asyncio
import json
import struct
from typing import Any

from pydantic import ValidationError

from app.schemas import ImageMeta
from app.utils.errors import HeaderParseError, ImageByteLengthMismatchError, ImageTooLargeError

MAX_HEADER_BYTES = 64 * 1024


def encode_request(header: dict[str, Any], image_bytes: bytes) -> bytes:
    header = dict(header)
    header.setdefault("image_len", len(image_bytes))
    header_bytes = json.dumps(header, ensure_ascii=False).encode("utf-8")
    if len(header_bytes) > MAX_HEADER_BYTES:
        raise HeaderParseError("header_json_length exceeds 64KB")
    return struct.pack(">I", len(header_bytes)) + header_bytes + image_bytes


async def decode_request_from_stream(
    reader: asyncio.StreamReader,
    max_image_bytes: int | None = None,
) -> tuple[ImageMeta, bytes]:
    try:
        header_len_bytes = await reader.readexactly(4)
        header_len = struct.unpack(">I", header_len_bytes)[0]
        if header_len <= 0 or header_len > MAX_HEADER_BYTES:
            raise HeaderParseError(f"invalid header length: {header_len}")
        header_bytes = await reader.readexactly(header_len)
        header = json.loads(header_bytes.decode("utf-8"))
        meta = ImageMeta(**header)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        raise HeaderParseError(f"header JSON parse failed: {exc}") from exc
    except asyncio.IncompleteReadError as exc:
        raise HeaderParseError("incomplete request header") from exc

    if max_image_bytes is not None and meta.image_len > max_image_bytes:
        raise ImageTooLargeError(
            f"image_len {meta.image_len} exceeds max_image_bytes {max_image_bytes}"
        )
    try:
        image_bytes = await reader.readexactly(meta.image_len)
    except asyncio.IncompleteReadError as exc:
        raise ImageByteLengthMismatchError("image bytes shorter than image_len") from exc
    return meta, image_bytes


def encode_response(response: dict[str, Any]) -> bytes:
    body = json.dumps(response, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(body)) + body


async def decode_response_from_stream(reader: asyncio.StreamReader) -> dict[str, Any]:
    try:
        length_bytes = await reader.readexactly(4)
        length = struct.unpack(">I", length_bytes)[0]
        if length <= 0 or length > MAX_HEADER_BYTES:
            raise HeaderParseError(f"invalid response length: {length}")
        body = await reader.readexactly(length)
        return json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HeaderParseError(f"response JSON parse failed: {exc}") from exc


# 旧接口保留为明确失败，防止继续使用旧 HEADER 标记协议。
def split_byte_stream(*_args, **_kwargs):
    raise NotImplementedError("use decode_request_from_stream")


def parse_payload(*_args, **_kwargs):
    raise NotImplementedError("use decode_request_from_stream")


def build_response_json(*_args, **_kwargs):
    raise NotImplementedError("use encode_response")


def wrap_packet(*_args, **_kwargs):
    raise NotImplementedError("use encode_request")
