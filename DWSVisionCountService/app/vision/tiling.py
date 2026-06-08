"""2x2 tile 推理窗口工具。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TileWindow:
    x1: int
    y1: int
    x2: int
    y2: int


def make_2x2_tile_windows(
    width: int,
    height: int,
    overlap_ratio: float = 0.1,
) -> list[TileWindow]:
    """返回 2x2 推理窗口。"""
    if width <= 1 or height <= 1:
        raise ValueError("tile source size must be greater than 1")
    if overlap_ratio < 0 or overlap_ratio >= 0.5:
        raise ValueError("overlap_ratio must be in [0, 0.5)")

    mid_x = width // 2
    mid_y = height // 2
    overlap_x = int(round(mid_x * overlap_ratio))
    overlap_y = int(round(mid_y * overlap_ratio))

    left_x2 = min(width, mid_x + overlap_x)
    right_x1 = max(0, mid_x - overlap_x)
    top_y2 = min(height, mid_y + overlap_y)
    bottom_y1 = max(0, mid_y - overlap_y)

    return [
        TileWindow(0, 0, left_x2, top_y2),
        TileWindow(right_x1, 0, width, top_y2),
        TileWindow(0, bottom_y1, left_x2, height),
        TileWindow(right_x1, bottom_y1, width, height),
    ]
