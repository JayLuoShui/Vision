from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(eq=True)
class Annotation:
    cls: int
    kind: str = "box"
    points: list[tuple[float, float]] = field(default_factory=list)
    conf: float | None = None

    @classmethod
    def from_box(cls, cls_idx: int, x1: float, y1: float, x2: float, y2: float, conf: float | None = None) -> "Annotation":
        return cls(int(cls_idx), "box", [(float(x1), float(y1)), (float(x2), float(y2))], conf)

    @classmethod
    def from_polygon(cls, cls_idx: int, points: list[tuple[float, float]], conf: float | None = None) -> "Annotation":
        return cls(int(cls_idx), "polygon", [(float(x), float(y)) for x, y in points], conf)

    def copy(self) -> "Annotation":
        return Annotation(self.cls, self.kind, list(self.points), self.conf)

    @property
    def is_box(self) -> bool:
        return self.kind == "box"

    @property
    def is_polygon(self) -> bool:
        return self.kind == "polygon"

    def box_corners(self) -> tuple[float, float, float, float]:
        if not self.is_box or len(self.points) < 2:
            return 0.0, 0.0, 0.0, 0.0
        return self.points[0][0], self.points[0][1], self.points[1][0], self.points[1][1]

    def bounds(self) -> tuple[float, float, float, float]:
        if self.is_box:
            x1, y1, x2, y2 = self.box_corners()
            left, right = sorted([x1, x2])
            top, bottom = sorted([y1, y2])
            return left, top, right, bottom
        if not self.points:
            return 0.0, 0.0, 0.0, 0.0
        xs = [point[0] for point in self.points]
        ys = [point[1] for point in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    def to_yolo_line(self, width: int, height: int) -> str | None:
        if width <= 0 or height <= 0:
            return None
        if self.is_box:
            x1, y1, x2, y2 = self.box_corners()
            x1 = max(0.0, min(float(width), x1))
            y1 = max(0.0, min(float(height), y1))
            x2 = max(0.0, min(float(width), x2))
            y2 = max(0.0, min(float(height), y2))
            left, right = sorted([x1, x2])
            top, bottom = sorted([y1, y2])
            box_width = right - left
            box_height = bottom - top
            if box_width < 1.0 or box_height < 1.0:
                return None
            cx = left + box_width / 2.0
            cy = top + box_height / 2.0
            return f"{self.cls} {cx / width:.6f} {cy / height:.6f} {box_width / width:.6f} {box_height / height:.6f}"
        if len(self.points) < 3:
            return None
        parts = [str(self.cls)]
        for x, y in self.points:
            parts.append(f"{max(0.0, min(float(width), x)) / width:.6f}")
            parts.append(f"{max(0.0, min(float(height), y)) / height:.6f}")
        return " ".join(parts)

    @staticmethod
    def from_yolo_line(line: str, width: int, height: int) -> "Annotation | None":
        parts = line.split()
        if len(parts) < 5:
            return None
        try:
            cls_idx = int(float(parts[0]))
            values = [float(item) for item in parts[1:]]
        except ValueError:
            return None
        if len(values) == 4:
            cx, cy, box_width, box_height = values
            return Annotation.from_box(
                cls_idx,
                round((cx - box_width / 2.0) * width, 3),
                round((cy - box_height / 2.0) * height, 3),
                round((cx + box_width / 2.0) * width, 3),
                round((cy + box_height / 2.0) * height, 3),
            )
        if len(values) >= 6 and len(values) % 2 == 0:
            return Annotation.from_polygon(
                cls_idx,
                [(round(values[i] * width, 3), round(values[i + 1] * height, 3)) for i in range(0, len(values), 2)],
            )
        return None
