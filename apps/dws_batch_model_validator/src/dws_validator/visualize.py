# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple
import cv2
import numpy as np

from .predictor import Detection
from .decision import Decision


def _color_for_status(status: str) -> Tuple[int, int, int]:
    if status == "SINGLE":
        return (0, 180, 0)
    if status == "MULTI":
        return (0, 0, 255)
    if status == "SUSPECT_MULTI":
        return (0, 165, 255)
    return (180, 180, 180)


def read_image_bgr(path: str | Path) -> Optional[np.ndarray]:
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def write_image_bgr(path: str | Path, image_bgr: np.ndarray) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = out_path.suffix or ".jpg"
    ok, encoded = cv2.imencode(suffix, image_bgr)
    if not ok:
        raise OSError(f"可视化图片编码失败：{out_path}")
    out_path.write_bytes(encoded.tobytes())


def draw_result(
    image_bgr: np.ndarray,
    detections: Sequence[Detection],
    decision: Decision,
    total_ms: float,
    out_path: Path,
    *,
    high_conf: float,
    low_conf: float,
    gt_count: Optional[int] = None,
) -> None:
    canvas = image_bgr.copy()
    h, w = canvas.shape[:2]
    status_color = _color_for_status(decision.status)

    overlay = canvas.copy()
    for d in detections:
        if d.conf < low_conf:
            continue
        color = status_color if d.conf >= high_conf else (0, 165, 255)
        if d.mask is not None:
            mask = d.mask
            if mask.shape[:2] != (h, w):
                mask = cv2.resize(mask.astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)
            mask_bin = mask > 0.5
            overlay[mask_bin] = (0.55 * overlay[mask_bin] + 0.45 * np.array(color)).astype(np.uint8)

    canvas = cv2.addWeighted(overlay, 0.75, canvas, 0.25, 0)

    for d in detections:
        if d.conf < low_conf:
            continue
        x1, y1, x2, y2 = [int(round(v)) for v in d.xyxy]
        color = status_color if d.conf >= high_conf else (0, 165, 255)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 3)
        label = f"parcel {d.conf:.2f}"
        if d.conf < high_conf:
            label += " suspect"
        cv2.putText(
            canvas,
            label,
            (max(5, x1), max(30, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            color,
            2,
            cv2.LINE_AA,
        )

    gt_text = "NA" if gt_count is None else str(gt_count)
    header = (
        f"status={decision.status}  pred_count={decision.pred_count}  "
        f"suspect={decision.suspect_count}  gt={gt_text}  total_ms={total_ms:.2f}"
    )

    cv2.rectangle(canvas, (0, 0), (w, 58), (0, 0, 0), -1)
    cv2.putText(
        canvas,
        header,
        (16, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.05,
        status_color,
        2,
        cv2.LINE_AA,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_image_bgr(out_path, canvas)
