"""TurboJPEG 原生 BGR 解码封装。"""

from __future__ import annotations

import ctypes
import os
import threading
from pathlib import Path

import numpy as np


class TurboJpegDecodeError(RuntimeError):
    """TurboJPEG DLL 加载或解码失败。"""


_DLL_NAME = "dws_turbojpeg_decoder.dll"
_ERROR_CAPACITY = 512
_load_lock = threading.Lock()
_library: ctypes.CDLL | None = None
_dll_directory_handle = None


def _native_bin_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "native" / "turbojpeg_decoder" / "bin"


def _load_library() -> ctypes.CDLL:
    global _library, _dll_directory_handle
    if _library is not None:
        return _library
    with _load_lock:
        if _library is not None:
            return _library
        native_dir = _native_bin_dir()
        library_path = native_dir / _DLL_NAME
        if not library_path.exists():
            raise TurboJpegDecodeError(
                f"原生 JPEG 解码模块不存在: {library_path}，请先运行 "
                "scripts/build_turbojpeg_decoder.ps1"
            )
        if hasattr(os, "add_dll_directory"):
            _dll_directory_handle = os.add_dll_directory(str(native_dir))
        try:
            library = ctypes.CDLL(str(library_path))
        except OSError as exc:
            raise TurboJpegDecodeError(f"加载原生 JPEG 解码模块失败: {exc}") from exc

        byte_pointer = ctypes.POINTER(ctypes.c_ubyte)
        library.dws_turbojpeg_get_info.argtypes = [
            byte_pointer,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        library.dws_turbojpeg_get_info.restype = ctypes.c_int
        library.dws_turbojpeg_decode_bgr.argtypes = [
            byte_pointer,
            ctypes.c_size_t,
            byte_pointer,
            ctypes.c_size_t,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        library.dws_turbojpeg_decode_bgr.restype = ctypes.c_int
        _library = library
        return library


def _error_message(buffer: ctypes.Array) -> str:
    message = buffer.value.decode("utf-8", errors="replace")
    return message or "unknown TurboJPEG error"


def decode_jpeg_bgr(image_bytes: bytes) -> np.ndarray:
    """把完整 JPEG bytes 解码为连续 BGR uint8 图像。"""
    if not image_bytes:
        raise TurboJpegDecodeError("JPEG bytes 为空")

    library = _load_library()
    source = np.frombuffer(image_bytes, dtype=np.uint8)
    source_pointer = source.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
    width = ctypes.c_int()
    height = ctypes.c_int()
    error = ctypes.create_string_buffer(_ERROR_CAPACITY)

    result = library.dws_turbojpeg_get_info(
        source_pointer,
        source.size,
        ctypes.byref(width),
        ctypes.byref(height),
        error,
        _ERROR_CAPACITY,
    )
    if result != 0:
        raise TurboJpegDecodeError(_error_message(error))

    output = np.empty((height.value, width.value, 3), dtype=np.uint8)
    error.value = b""
    result = library.dws_turbojpeg_decode_bgr(
        source_pointer,
        source.size,
        output.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte)),
        output.nbytes,
        width.value,
        height.value,
        error,
        _ERROR_CAPACITY,
    )
    if result != 0:
        raise TurboJpegDecodeError(_error_message(error))
    return output


def verify_turbojpeg_available() -> None:
    """确认原生解码 DLL 及其依赖可以加载。"""
    _load_library()
