from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from cvds_annotation_tool.constants import DEFECT_KINDS, DEFECT_SEVERITIES, DEFECT_TYPES
from cvds_annotation_tool.models.annotation import Annotation


@dataclass(eq=True)
class DefectAnnotation:
    defect_id: str
    parent_index: int
    parent_cls: int
    defect_type: str = "hole"
    severity: str = "medium"
    kind: str = "polygon"
    points: list[tuple[float, float]] = field(default_factory=list)
    note: str = ""
    created_at: str = ""

    @classmethod
    def from_polygon(
        cls,
        parent_index: int,
        parent: Annotation,
        defect_type: str,
        severity: str,
        points: list[tuple[float, float]],
        note: str = "",
    ) -> "DefectAnnotation":
        return cls._create(parent_index, parent, defect_type, severity, "polygon", points, note)

    @classmethod
    def from_box(
        cls,
        parent_index: int,
        parent: Annotation,
        defect_type: str,
        severity: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        note: str = "",
    ) -> "DefectAnnotation":
        return cls._create(parent_index, parent, defect_type, severity, "box", [(x1, y1), (x2, y2)], note)

    @classmethod
    def from_point(
        cls,
        parent_index: int,
        parent: Annotation,
        defect_type: str,
        severity: str,
        x: float,
        y: float,
        note: str = "",
    ) -> "DefectAnnotation":
        return cls._create(parent_index, parent, defect_type, severity, "point", [(x, y)], note)

    @classmethod
    def _create(
        cls,
        parent_index: int,
        parent: Annotation,
        defect_type: str,
        severity: str,
        kind: str,
        points: list[tuple[float, float]],
        note: str,
    ) -> "DefectAnnotation":
        return cls(
            defect_id=uuid.uuid4().hex[:12],
            parent_index=int(parent_index),
            parent_cls=int(parent.cls),
            defect_type=defect_type if defect_type in DEFECT_TYPES else "other",
            severity=severity if severity in DEFECT_SEVERITIES else "medium",
            kind=kind if kind in DEFECT_KINDS else "polygon",
            points=[(float(x), float(y)) for x, y in points],
            note=note,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )

    def copy(self) -> "DefectAnnotation":
        return DefectAnnotation(
            self.defect_id,
            self.parent_index,
            self.parent_cls,
            self.defect_type,
            self.severity,
            self.kind,
            list(self.points),
            self.note,
            self.created_at,
        )

    def is_valid(self) -> bool:
        if self.kind == "point":
            return len(self.points) == 1
        if self.kind == "box":
            if len(self.points) < 2:
                return False
            return abs(self.points[1][0] - self.points[0][0]) >= 1 and abs(self.points[1][1] - self.points[0][1]) >= 1
        return len(self.points) >= 3

    def to_json(self, width: int, height: int, labels: list[str]) -> dict:
        parent_label = labels[self.parent_cls] if 0 <= self.parent_cls < len(labels) else str(self.parent_cls)
        return {
            "id": self.defect_id,
            "parent_index": self.parent_index,
            "parent_cls": self.parent_cls,
            "parent_label": parent_label,
            "type": self.defect_type,
            "severity": self.severity,
            "kind": self.kind,
            "points": [
                [
                    round(max(0.0, min(float(width), x)) / max(1, width), 6),
                    round(max(0.0, min(float(height), y)) / max(1, height), 6),
                ]
                for x, y in self.points
            ],
            "note": self.note,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_json(item: dict, width: int, height: int) -> "DefectAnnotation | None":
        kind = str(item.get("kind") or "polygon")
        if kind not in DEFECT_KINDS:
            kind = "polygon"
        points: list[tuple[float, float]] = []
        for raw_point in item.get("points") or []:
            if isinstance(raw_point, (list, tuple)) and len(raw_point) == 2:
                try:
                    points.append((float(raw_point[0]) * width, float(raw_point[1]) * height))
                except (TypeError, ValueError):
                    pass
        defect = DefectAnnotation(
            defect_id=str(item.get("id") or uuid.uuid4().hex[:12]),
            parent_index=int(item.get("parent_index", -1)),
            parent_cls=int(item.get("parent_cls", 0)),
            defect_type=str(item.get("type") or "other"),
            severity=str(item.get("severity") or "medium"),
            kind=kind,
            points=points,
            note=str(item.get("note") or ""),
            created_at=str(item.get("created_at") or ""),
        )
        defect.defect_type = defect.defect_type if defect.defect_type in DEFECT_TYPES else "other"
        defect.severity = defect.severity if defect.severity in DEFECT_SEVERITIES else "medium"
        return defect if defect.is_valid() else None


def reindex_defects_after_delete(defects: list[DefectAnnotation], deleted_index: int) -> list[DefectAnnotation]:
    updated: list[DefectAnnotation] = []
    for defect in defects:
        if defect.parent_index == deleted_index:
            continue
        copied = defect.copy()
        if copied.parent_index > deleted_index:
            copied.parent_index -= 1
        updated.append(copied)
    return updated


def sync_defect_parent_class(defects: list[DefectAnnotation], annotations: list[Annotation]) -> None:
    for defect in defects:
        if 0 <= defect.parent_index < len(annotations):
            defect.parent_cls = annotations[defect.parent_index].cls
