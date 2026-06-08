"""内存图片解码工具。

生产主链路只接收 bytes，不接收 base64、文件路径或共享目录输入。
"""

from __future__ import annotations

import cv2
import numpy as np

from app.schemas import DecodedImage, ImageMeta
from app.utils.errors import (
    ImageByteLengthMismatchError,
    ImageDecodeError,
    ImageEmptyError,
    RawImageParamMissingError,
)
from app.utils.turbojpeg_decoder import TurboJpegDecodeError, decode_jpeg_bgr

ENCODED_FORMATS = {"encoded", "jpg", "jpeg", "png", "bmp"}
RAW_FORMATS = {"raw_bgr", "raw_rgb", "raw_gray"}
JPEG_FORMATS = {"jpg", "jpeg"}

REDUCED_DECODE_FLAGS = {
    1: cv2.IMREAD_COLOR,
    2: cv2.IMREAD_REDUCED_COLOR_2,
    4: cv2.IMREAD_REDUCED_COLOR_4,
    8: cv2.IMREAD_REDUCED_COLOR_8,
}


def decode_image_bytes(meta: ImageMeta, image_bytes: bytes) -> np.ndarray:
    """按 header 描述把图片 bytes 解码为 BGR 图像。"""
    return decode_image_bytes_with_info(meta, image_bytes).image_bgr


def decode_image_bytes_with_info(
    meta: ImageMeta,
    image_bytes: bytes,
    reduce_factor: int = 1,
) -> DecodedImage:
    """按 header 解码图片，并返回原始尺寸与解码缩放信息。"""
    if not image_bytes:
        raise ImageEmptyError("image_bytes is empty")
    if len(image_bytes) != meta.image_len:
        raise ImageByteLengthMismatchError(
            f"image_len mismatch: header={meta.image_len}, actual={len(image_bytes)}"
        )

    encoding = (meta.image_encoding or "encoded").lower()
    if encoding in ENCODED_FORMATS:
        image, original_width, original_height = _decode_encoded_with_size(
            image_bytes,
            encoding,
            meta,
            reduce_factor,
        )
        height, width = image.shape[:2]
        return DecodedImage(
            task_id=meta.task_id,
            image_bgr=image,
            width=width,
            height=height,
            original_width=original_width,
            original_height=original_height,
            decode_scale_x=width / original_width,
            decode_scale_y=height / original_height,
            source_encoding=meta.image_encoding,
        )
    if encoding in RAW_FORMATS:
        image = _decode_raw(meta, image_bytes, encoding)
        height, width = image.shape[:2]
        return DecodedImage(
            task_id=meta.task_id,
            image_bgr=image,
            width=width,
            height=height,
            original_width=width,
            original_height=height,
            source_encoding=meta.image_encoding,
        )
    raise ImageDecodeError(f"unsupported image_encoding: {meta.image_encoding}")


def _decode_encoded(image_bytes: bytes) -> np.ndarray:
    image, _, _ = _decode_encoded_with_size(
        image_bytes,
        "encoded",
        ImageMeta(task_id="", image_encoding="encoded", image_len=len(image_bytes)),
        1,
    )
    return image


def _decode_encoded_with_size(
    image_bytes: bytes,
    encoding: str,
    meta: ImageMeta,
    reduce_factor: int,
) -> tuple[np.ndarray, int, int]:
    if reduce_factor not in REDUCED_DECODE_FLAGS:
        raise ImageDecodeError(f"unsupported decode_reduce_factor: {reduce_factor}")
    encoded_format = _encoded_format(encoding, image_bytes)
    flag = REDUCED_DECODE_FLAGS[reduce_factor] if encoded_format in JPEG_FORMATS else cv2.IMREAD_COLOR
    try:
        if encoded_format in JPEG_FORMATS and reduce_factor == 1:
            image = decode_jpeg_bgr(image_bytes)
        else:
            arr = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(arr, flag)
    except TurboJpegDecodeError as exc:
        raise ImageDecodeError(f"TurboJPEG decode failed: {exc}") from exc
    if image is None or image.size == 0:
        raise ImageDecodeError("image decoder returned empty image")
    height, width = image.shape[:2]
    original_width = int(meta.width or 0)
    original_height = int(meta.height or 0)
    if original_width <= 0 or original_height <= 0:
        original_width, original_height = _encoded_image_size(image_bytes, encoded_format)
    if original_width <= 0 or original_height <= 0:
        original_width, original_height = width, height
    return image, original_width, original_height


def _encoded_format(encoding: str, image_bytes: bytes) -> str:
    if encoding in {"jpg", "jpeg", "png", "bmp"}:
        return "jpg" if encoding == "jpeg" else encoding
    if image_bytes.startswith(b"\xff\xd8"):
        return "jpg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if image_bytes.startswith(b"BM"):
        return "bmp"
    return "encoded"


def _encoded_image_size(image_bytes: bytes, encoded_format: str) -> tuple[int, int]:
    if encoded_format in JPEG_FORMATS:
        return _jpeg_size(image_bytes)
    if encoded_format == "png" and len(image_bytes) >= 24:
        return int.from_bytes(image_bytes[16:20], "big"), int.from_bytes(image_bytes[20:24], "big")
    if encoded_format == "bmp" and len(image_bytes) >= 26:
        return int.from_bytes(image_bytes[18:22], "little"), abs(int.from_bytes(image_bytes[22:26], "little", signed=True))
    return 0, 0


def _jpeg_size(image_bytes: bytes) -> tuple[int, int]:
    index = 2
    while index + 9 < len(image_bytes):
        if image_bytes[index] != 0xFF:
            index += 1
            continue
        marker = image_bytes[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(image_bytes):
            break
        segment_length = int.from_bytes(image_bytes[index : index + 2], "big")
        if segment_length < 2:
            break
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            start = index + 2
            if start + 5 <= len(image_bytes):
                height = int.from_bytes(image_bytes[start + 1 : start + 3], "big")
                width = int.from_bytes(image_bytes[start + 3 : start + 5], "big")
                return width, height
        index += segment_length
    return 0, 0


def _require_raw_shape(meta: ImageMeta, encoding: str) -> tuple[int, int, int]:
    if meta.width is None or meta.height is None:
        raise RawImageParamMissingError("raw image needs width and height")
    expected_channels = 1 if encoding == "raw_gray" else 3
    if meta.channels is None:
        raise RawImageParamMissingError("raw image needs channels")
    if meta.channels != expected_channels:
        raise RawImageParamMissingError(
            f"{encoding} needs channels={expected_channels}, got {meta.channels}"
        )
    return int(meta.width), int(meta.height), int(meta.channels)


def _decode_raw(meta: ImageMeta, image_bytes: bytes, encoding: str) -> np.ndarray:
    width, height, channels = _require_raw_shape(meta, encoding)
    expected_len = width * height * channels
    if len(image_bytes) != expected_len:
        raise ImageByteLengthMismatchError(
            f"raw byte length mismatch: expected={expected_len}, actual={len(image_bytes)}"
        )

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    if encoding == "raw_gray":
        gray = arr.reshape((height, width))
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    image = arr.reshape((height, width, channels))
    if encoding == "raw_rgb":
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    return image


def decode_image(data: bytes) -> tuple[np.ndarray | None, int, int]:
    """兼容旧调用：只解码 encoded bytes，失败返回空结果。"""
    try:
        meta = ImageMeta(task_id="", image_encoding="encoded", image_len=len(data))
        image = decode_image_bytes(meta, data)
        height, width = image.shape[:2]
        return image, width, height
    except Exception:
        return None, 0, 0
