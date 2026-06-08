"""兼容旧导入路径的几何工具。"""

from __future__ import annotations

from app.vision.geometry import (
    box_area as _box_area,
    box_center,
    box_iou,
    point_in_polygon as _point_in_polygon,
)


def box_area(*args) -> float:
    if len(args) == 1:
        return _box_area(args[0])
    return _box_area([args[0], args[1], args[2], args[3]])


def center_of_box(*args) -> tuple[float, float]:
    center = box_center(args[0] if len(args) == 1 else [args[0], args[1], args[2], args[3]])
    return (center[0], center[1])


def iou(box_a: list[float], box_b: list[float]) -> float:
    return box_iou(box_a, box_b)


def point_in_polygon(*args) -> bool:
    if len(args) == 2:
        return _point_in_polygon(args[0], args[1])
    return _point_in_polygon([args[0], args[1]], args[2])
