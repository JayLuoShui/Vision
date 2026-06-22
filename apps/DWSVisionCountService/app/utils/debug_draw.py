"""调试图绘制。"""

from __future__ import annotations

import cv2
import numpy as np

from app.schemas import CountObject


def draw_debug_image(
    image_bgr: np.ndarray,
    objects: list[CountObject],
    belt_polygon: list[list[int]],
    parcel_count: int,
    processing_time_ms: int,
    original_width: int | None = None,
    original_height: int | None = None,
) -> np.ndarray:
    """绘制检测框、多边形和计数结果。"""
    canvas = image_bgr.copy()
    height, width = canvas.shape[:2]
    scale_x = width / original_width if original_width else 1.0
    scale_y = height / original_height if original_height else 1.0
    polygon = np.array(
        [[int(round(x * scale_x)), int(round(y * scale_y))] for x, y in belt_polygon],
        dtype=np.int32,
    ).reshape((-1, 1, 2))
    cv2.polylines(canvas, [polygon], True, (0, 255, 255), 3)
    for obj in objects:
        x1 = int(round(obj.box[0] * scale_x))
        y1 = int(round(obj.box[1] * scale_y))
        x2 = int(round(obj.box[2] * scale_x))
        y2 = int(round(obj.box[3] * scale_y))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(canvas, f"{obj.score:.2f}", (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    cv2.putText(
        canvas,
        f"count={parcel_count} time={processing_time_ms}ms",
        (30, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (0, 255, 255),
        3,
    )
    return canvas
