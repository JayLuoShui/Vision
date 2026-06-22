"""与 Tk 界面解耦的 ROI 坐标映射和编辑状态。"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, TypeAlias


Point: TypeAlias = tuple[int, int]
Rect: TypeAlias = tuple[int, int, int, int]
EditMode: TypeAlias = Literal["detect_rect", "belt_polygon", "ignore_rect"]

SUPPORTED_MODES: tuple[EditMode, ...] = (
    "detect_rect",
    "belt_polygon",
    "ignore_rect",
)


def _read_point(point: tuple[float, float]) -> tuple[float, float]:
    if len(point) != 2:
        raise ValueError("Point must contain exactly two coordinates")
    x, y = float(point[0]), float(point[1])
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("Point coordinates must be finite")
    return x, y


def _round_coordinate(value: float) -> int:
    return int(math.floor(value + 0.5))


def _validate_size(name: str, size: tuple[int, int]) -> None:
    if len(size) != 2 or any(isinstance(value, bool) for value in size):
        raise ValueError(f"{name} must contain two positive numbers")
    if any(not isinstance(value, (int, float)) for value in size):
        raise ValueError(f"{name} must contain two positive numbers")
    if any(not math.isfinite(value) or value <= 0 for value in size):
        raise ValueError(f"{name} must contain two positive numbers")


def _validate_mode(mode: str) -> EditMode:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported ROI edit mode: {mode}")
    return mode


@dataclass(frozen=True)
class CanvasTransform:
    """把原图等比居中放入画布，并提供双向点转换。"""

    image_size: tuple[int, int]
    canvas_size: tuple[int, int]

    def __post_init__(self) -> None:
        _validate_size("image_size", self.image_size)
        _validate_size("canvas_size", self.canvas_size)
        if any(not isinstance(value, int) for value in self.image_size):
            raise ValueError("image_size must contain two positive integers")

    @property
    def scale(self) -> float:
        image_width, image_height = self.image_size
        canvas_width, canvas_height = self.canvas_size
        return min(canvas_width / image_width, canvas_height / image_height)

    @property
    def rendered_size(self) -> tuple[float, float]:
        image_width, image_height = self.image_size
        return image_width * self.scale, image_height * self.scale

    @property
    def offset(self) -> tuple[float, float]:
        canvas_width, canvas_height = self.canvas_size
        rendered_width, rendered_height = self.rendered_size
        return (
            (canvas_width - rendered_width) / 2.0,
            (canvas_height - rendered_height) / 2.0,
        )

    def image_to_canvas(self, point: tuple[float, float]) -> tuple[float, float]:
        x, y = _read_point(point)
        image_width, image_height = self.image_size
        if not 0 <= x <= image_width or not 0 <= y <= image_height:
            raise ValueError("Image point is outside the image bounds")
        offset_x, offset_y = self.offset
        return offset_x + x * self.scale, offset_y + y * self.scale

    def canvas_to_image(self, point: tuple[float, float]) -> tuple[float, float]:
        x, y = _read_point(point)
        offset_x, offset_y = self.offset
        rendered_width, rendered_height = self.rendered_size
        if not (
            offset_x <= x <= offset_x + rendered_width
            and offset_y <= y <= offset_y + rendered_height
        ):
            raise ValueError("Canvas point is outside the rendered image")
        return (x - offset_x) / self.scale, (y - offset_y) / self.scale


@dataclass(frozen=True)
class _Snapshot:
    detect_rect: Rect | None
    belt_polygon: tuple[Point, ...]
    ignore_rects: tuple[Rect, ...]


class ROIEditorState:
    """保存三类 ROI 编辑结果和可撤销历史。"""

    def __init__(
        self,
        image_size: tuple[int, int],
        canvas_size: tuple[int, int],
        mode: EditMode = "detect_rect",
    ) -> None:
        self.transform = CanvasTransform(image_size, canvas_size)
        self._mode = _validate_mode(mode)
        self._detect_rect: Rect | None = None
        self._belt_polygon: list[Point] = []
        self._ignore_rects: list[Rect] = []
        self._history: list[_Snapshot] = []

    @property
    def mode(self) -> EditMode:
        return self._mode

    @property
    def detect_rect(self) -> Rect | None:
        return self._detect_rect

    @property
    def belt_polygon(self) -> list[Point]:
        return list(self._belt_polygon)

    @property
    def ignore_rects(self) -> list[Rect]:
        return list(self._ignore_rects)

    def set_mode(self, mode: EditMode) -> None:
        self._mode = _validate_mode(mode)

    def set_canvas_size(self, canvas_size: tuple[int, int]) -> None:
        self.transform = CanvasTransform(self.transform.image_size, canvas_size)

    def load_existing(
        self,
        detect_rect: Rect | None,
        belt_polygon: list[Point],
        ignore_rects: list[Rect],
    ) -> None:
        image_width, image_height = self.transform.image_size
        points = list(belt_polygon)
        rects = ([detect_rect] if detect_rect is not None else []) + list(ignore_rects)
        for x, y in points:
            if not 0 <= x <= image_width or not 0 <= y <= image_height:
                raise ValueError("ROI point is outside image bounds")
        for x1, y1, x2, y2 in rects:
            if not (
                0 <= x1 < x2 <= image_width
                and 0 <= y1 < y2 <= image_height
            ):
                raise ValueError("ROI rectangle is outside image bounds")
        self._detect_rect = detect_rect
        self._belt_polygon = points
        self._ignore_rects = list(ignore_rects)
        self._history.clear()

    def add_point(self, canvas_point: tuple[float, float]) -> Point:
        if self._mode != "belt_polygon":
            raise ValueError("add_point is only valid in belt_polygon mode")
        point = self._canvas_point_to_image_int(canvas_point)
        self._save_history()
        self._belt_polygon.append(point)
        return point

    def add_rectangle(
        self,
        canvas_start: tuple[float, float],
        canvas_end: tuple[float, float],
    ) -> Rect:
        if self._mode not in {"detect_rect", "ignore_rect"}:
            raise ValueError(
                "add_rectangle is only valid in detect_rect or ignore_rect mode"
            )
        start_x, start_y = self._canvas_point_to_image_int(canvas_start)
        end_x, end_y = self._canvas_point_to_image_int(canvas_end)
        rect = (
            min(start_x, end_x),
            min(start_y, end_y),
            max(start_x, end_x),
            max(start_y, end_y),
        )
        if rect[0] == rect[2] or rect[1] == rect[3]:
            raise ValueError("Rectangle must have non-zero width and height")

        self._save_history()
        if self._mode == "detect_rect":
            self._detect_rect = rect
        else:
            self._ignore_rects.append(rect)
        return rect

    def undo(self) -> bool:
        if not self._history:
            return False
        snapshot = self._history.pop()
        self._detect_rect = snapshot.detect_rect
        self._belt_polygon = list(snapshot.belt_polygon)
        self._ignore_rects = list(snapshot.ignore_rects)
        return True

    def clear(self, mode: EditMode | None = None) -> None:
        selected_mode = self._mode if mode is None else _validate_mode(mode)
        if not self._has_value(selected_mode):
            return
        self._save_history()
        if selected_mode == "detect_rect":
            self._detect_rect = None
        elif selected_mode == "belt_polygon":
            self._belt_polygon.clear()
        else:
            self._ignore_rects.clear()

    def export(
        self,
        mode: EditMode | None = None,
    ) -> list[int] | list[list[int]]:
        selected_mode = self._mode if mode is None else _validate_mode(mode)
        if selected_mode == "detect_rect":
            if self._detect_rect is None:
                raise ValueError("detect_rect has not been defined")
            return list(self._detect_rect)
        if selected_mode == "belt_polygon":
            if len(self._belt_polygon) < 3:
                raise ValueError("belt_polygon must contain at least 3 points")
            return [list(point) for point in self._belt_polygon]
        return [list(rect) for rect in self._ignore_rects]

    def _canvas_point_to_image_int(
        self,
        canvas_point: tuple[float, float],
    ) -> Point:
        x, y = self.transform.canvas_to_image(canvas_point)
        return _round_coordinate(x), _round_coordinate(y)

    def _save_history(self) -> None:
        self._history.append(
            _Snapshot(
                detect_rect=self._detect_rect,
                belt_polygon=tuple(self._belt_polygon),
                ignore_rects=tuple(self._ignore_rects),
            )
        )

    def _has_value(self, mode: EditMode) -> bool:
        if mode == "detect_rect":
            return self._detect_rect is not None
        if mode == "belt_polygon":
            return bool(self._belt_polygon)
        return bool(self._ignore_rects)
