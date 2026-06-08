"""视觉坐标几何工具。"""

from __future__ import annotations


def restore_box_to_original(
    box: list[float],
    roi_rect: list[int] | tuple[int, int, int, int],
    scale: float,
    pad_x: float,
    pad_y: float,
) -> list[float]:
    """把模型输入坐标还原到原图坐标。"""
    if scale <= 0:
        raise ValueError("scale must be positive")
    roi_x1, roi_y1, _, _ = roi_rect
    x1, y1, x2, y2 = box
    return [
        (x1 - pad_x) / scale + roi_x1,
        (y1 - pad_y) / scale + roi_y1,
        (x2 - pad_x) / scale + roi_x1,
        (y2 - pad_y) / scale + roi_y1,
    ]


def point_in_polygon(point: list[float] | tuple[float, float], polygon: list[list[int]]) -> bool:
    """判断点是否在多边形内，边界算在内。"""
    x, y = point
    inside = False
    count = len(polygon)
    if count < 3:
        return False
    prev = count - 1
    for curr in range(count):
        xi, yi = polygon[curr]
        xj, yj = polygon[prev]
        cross = (x - xi) * (yj - yi) - (y - yi) * (xj - xi)
        on_edge = (
            abs(cross) < 1e-9
            and min(xi, xj) <= x <= max(xi, xj)
            and min(yi, yj) <= y <= max(yi, yj)
        )
        if on_edge:
            return True
        if (yi > y) != (yj > y):
            x_at_y = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x <= x_at_y:
                inside = not inside
        prev = curr
    return inside


def box_area(box: list[float] | tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def box_center(box: list[float] | tuple[float, float, float, float]) -> list[float]:
    x1, y1, x2, y2 = box
    return [(x1 + x2) / 2.0, (y1 + y2) / 2.0]


def box_iou(box_a: list[float], box_b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter = box_area([max(ax1, bx1), max(ay1, by1), min(ax2, bx2), min(ay2, by2)])
    union = box_area(box_a) + box_area(box_b) - inter
    if union <= 0:
        return 0.0
    return inter / union


def clip_box_to_image(box: list[float], width: int, height: int) -> list[float]:
    x1, y1, x2, y2 = box
    return [
        max(0.0, min(float(width), x1)),
        max(0.0, min(float(height), y1)),
        max(0.0, min(float(width), x2)),
        max(0.0, min(float(height), y2)),
    ]
