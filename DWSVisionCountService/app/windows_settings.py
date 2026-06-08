"""Windows GUI 设置校验与 Config 构建。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from app.config import Config, DetectROIRect, IgnoreRegion


@dataclass(frozen=True)
class IgnoreRectDraft:
    name: str
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class SettingsDraft:
    tcp_port: int
    model_path: str
    confidence_threshold: float
    iou_threshold: float
    inference_num_threads: int
    decode_reduce_factor: int
    save_debug_image: bool
    image_width: int
    image_height: int
    detect_roi_rect: tuple[int, int, int, int]
    belt_polygon: tuple[tuple[int, int], ...]
    ignore_regions: tuple[IgnoreRectDraft, ...]


def _orientation(
    p: tuple[int, int],
    q: tuple[int, int],
    r: tuple[int, int],
) -> int:
    value = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
    return 0 if value == 0 else (1 if value > 0 else 2)


def _on_segment(
    p: tuple[int, int],
    q: tuple[int, int],
    r: tuple[int, int],
) -> bool:
    return (
        min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
        and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
    )


def _segments_intersect(
    p1: tuple[int, int],
    q1: tuple[int, int],
    p2: tuple[int, int],
    q2: tuple[int, int],
) -> bool:
    o1 = _orientation(p1, q1, p2)
    o2 = _orientation(p1, q1, q2)
    o3 = _orientation(p2, q2, p1)
    o4 = _orientation(p2, q2, q1)
    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and _on_segment(p1, p2, q1))
        or (o2 == 0 and _on_segment(p1, q2, q1))
        or (o3 == 0 and _on_segment(p2, p1, q2))
        or (o4 == 0 and _on_segment(p2, q1, q2))
    )


def _polygon_self_intersects(points: tuple[tuple[int, int], ...]) -> bool:
    edge_count = len(points)
    for first in range(edge_count):
        first_end = (first + 1) % edge_count
        for second in range(first + 1, edge_count):
            second_end = (second + 1) % edge_count
            if first in {second, second_end} or first_end in {second, second_end}:
                continue
            if _segments_intersect(
                points[first],
                points[first_end],
                points[second],
                points[second_end],
            ):
                return True
    return False


def _polygon_area_twice(points: tuple[tuple[int, int], ...]) -> int:
    return abs(
        sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(
                points,
                points[1:] + points[:1],
                strict=True,
            )
        )
    )


def _validate_rect(
    rect: tuple[int, int, int, int],
    width: int,
    height: int,
    label: str,
) -> None:
    x1, y1, x2, y2 = rect
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError(f"{label}超出图片范围或面积为零")


def _resolve_model_path(model_path: str, app_root: Path) -> Path:
    path = Path(model_path)
    return path if path.is_absolute() else app_root / path


def build_config(current: Config, draft: SettingsDraft, app_root: Path) -> Config:
    """严格校验 GUI 输入，并返回不影响运行中服务的新配置。"""
    if not 1 <= draft.tcp_port <= 65535:
        raise ValueError("TCP 端口必须在 1 到 65535 之间")
    if not 0.0 <= draft.confidence_threshold <= 1.0:
        raise ValueError("置信度必须在 0 到 1 之间")
    if not 0.0 <= draft.iou_threshold <= 1.0:
        raise ValueError("IoU 必须在 0 到 1 之间")
    if draft.inference_num_threads < 1:
        raise ValueError("推理线程必须大于 0")
    if draft.decode_reduce_factor not in {1, 2, 4, 8}:
        raise ValueError("JPEG reduce 倍率只能是 1、2、4 或 8")
    if draft.image_width < 1 or draft.image_height < 1:
        raise ValueError("必须先选择有效图片")
    if not _resolve_model_path(draft.model_path, app_root).is_dir():
        raise ValueError("模型目录不存在")

    _validate_rect(
        draft.detect_roi_rect,
        draft.image_width,
        draft.image_height,
        "检测区域",
    )
    if len(draft.belt_polygon) < 3:
        raise ValueError("输送带多边形至少需要三个点")
    if len(set(draft.belt_polygon)) != len(draft.belt_polygon):
        raise ValueError("输送带多边形不能包含重复点")
    for x, y in draft.belt_polygon:
        if not (0 <= x <= draft.image_width and 0 <= y <= draft.image_height):
            raise ValueError("输送带多边形超出图片范围")
    if _polygon_self_intersects(draft.belt_polygon):
        raise ValueError("输送带多边形不能自相交")
    if _polygon_area_twice(draft.belt_polygon) == 0:
        raise ValueError("输送带多边形面积不能为零")
    for region in draft.ignore_regions:
        _validate_rect(
            (region.x1, region.y1, region.x2, region.y2),
            draft.image_width,
            draft.image_height,
            "忽略区域",
        )

    updated = deepcopy(current)
    updated.service.tcp_port = draft.tcp_port
    updated.service.decode_reduce_factor = draft.decode_reduce_factor
    updated.model.model_path = draft.model_path
    updated.model.confidence_threshold = draft.confidence_threshold
    updated.model.iou_threshold = draft.iou_threshold
    updated.model.inference_num_threads = draft.inference_num_threads
    updated.debug.save_debug_image = draft.save_debug_image
    updated.camera.raw_width = draft.image_width
    updated.camera.raw_height = draft.image_height
    updated.detect_roi_rect = DetectROIRect(*draft.detect_roi_rect)
    updated.belt_polygon = [list(point) for point in draft.belt_polygon]
    updated.ignore_regions = [
        IgnoreRegion(
            name=region.name,
            x1=region.x1,
            y1=region.y1,
            x2=region.x2,
            y2=region.y2,
        )
        for region in draft.ignore_regions
    ]
    return updated
