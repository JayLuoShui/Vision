"""异步保存调试文件。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def save_image_async(path: str | Path, image_bgr: np.ndarray) -> None:
    """后台保存图片，不阻塞主链路。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _EXECUTOR.submit(cv2.imwrite, str(path), image_bgr)


def save_json_async(path: str | Path, data: dict) -> None:
    """后台保存 JSON，不写入 image_bytes。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def _write() -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    _EXECUTOR.submit(_write)
