from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.schemas import ImageMeta
from app.utils.errors import (
    ImageByteLengthMismatchError,
    ImageDecodeError,
    RawImageParamMissingError,
)
from app.utils.image_io import decode_image_bytes, decode_image_bytes_with_info
from app.utils.turbojpeg_decoder import decode_jpeg_bgr


def _meta(data: bytes, encoding: str = "jpg", **kwargs) -> ImageMeta:
    return ImageMeta(task_id="t1", image_encoding=encoding, image_len=len(data), **kwargs)


def test_jpg_bytes_decode():
    image = np.full((32, 40, 3), 120, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    decoded = decode_image_bytes(_meta(bytes(encoded), "jpg"), bytes(encoded))
    assert decoded.shape == (32, 40, 3)


def test_turbojpeg_decode_is_pixel_identical_to_opencv():
    rng = np.random.default_rng(42)
    image = rng.integers(0, 256, (127, 193, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 93])
    assert ok

    expected = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    actual = decode_jpeg_bgr(bytes(encoded))

    assert np.array_equal(actual, expected)


def test_full_jpg_decode_uses_turbojpeg(monkeypatch):
    image = np.full((32, 40, 3), 120, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    calls = 0

    def fake_decode(data: bytes) -> np.ndarray:
        nonlocal calls
        calls += 1
        return np.full((32, 40, 3), 77, dtype=np.uint8)

    monkeypatch.setattr("app.utils.image_io.decode_jpeg_bgr", fake_decode)
    decoded = decode_image_bytes(_meta(bytes(encoded), "jpg"), bytes(encoded))

    assert calls == 1
    assert np.all(decoded == 77)


def test_jpg_reduce_decode_keeps_original_size_metadata():
    image = np.full((64, 80, 3), 120, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    decoded = decode_image_bytes_with_info(_meta(bytes(encoded), "jpg"), bytes(encoded), reduce_factor=2)
    assert decoded.image_bgr.shape[:2] == (32, 40)
    assert decoded.width == 40
    assert decoded.height == 32
    assert decoded.original_width == 80
    assert decoded.original_height == 64
    assert decoded.decode_scale_x == pytest.approx(0.5)
    assert decoded.decode_scale_y == pytest.approx(0.5)


def test_png_bytes_decode():
    image = np.full((32, 40, 3), 120, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    decoded = decode_image_bytes(_meta(bytes(encoded), "png"), bytes(encoded))
    assert decoded.shape == (32, 40, 3)


def test_raw_bgr_bytes_decode():
    image = np.zeros((3, 4, 3), dtype=np.uint8)
    image[:, :, 0] = 10
    data = image.tobytes()
    decoded = decode_image_bytes(_meta(data, "raw_bgr", width=4, height=3, channels=3), data)
    assert decoded.shape == (3, 4, 3)
    assert decoded[0, 0, 0] == 10


def test_raw_rgb_bytes_decode():
    image = np.zeros((3, 4, 3), dtype=np.uint8)
    image[:, :, 0] = 255
    data = image.tobytes()
    decoded = decode_image_bytes(_meta(data, "raw_rgb", width=4, height=3, channels=3), data)
    assert decoded[0, 0, 2] == 255


def test_image_len_mismatch():
    meta = ImageMeta(task_id="t1", image_encoding="jpg", image_len=99)
    with pytest.raises(ImageByteLengthMismatchError):
        decode_image_bytes(meta, b"abc")


def test_raw_missing_shape():
    with pytest.raises(RawImageParamMissingError):
        decode_image_bytes(_meta(b"123", "raw_bgr"), b"123")


def test_bad_encoded_bytes():
    with pytest.raises(ImageDecodeError):
        decode_image_bytes(_meta(b"not-image", "jpg"), b"not-image")
