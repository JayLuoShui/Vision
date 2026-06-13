from __future__ import annotations

from dataclasses import dataclass, field

from cvds_annotation_tool.models.annotation import Annotation
from cvds_annotation_tool.models.defect import DefectAnnotation


@dataclass(eq=True)
class Snapshot:
    annotations: list[Annotation] = field(default_factory=list)
    defects: list[DefectAnnotation] = field(default_factory=list)
    selected: int = -1
    selected_defect: int = -1


class HistoryManager:
    def __init__(self, max_size: int = 100) -> None:
        self.max_size = max_size
        self.undo_stack: list[Snapshot] = []
        self.redo_stack: list[Snapshot] = []

    def push(self, snapshot: Snapshot) -> None:
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.max_size:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self, current: Snapshot) -> Snapshot | None:
        if not self.undo_stack:
            return None
        self.redo_stack.append(current)
        return self.undo_stack.pop()

    def redo(self, current: Snapshot) -> Snapshot | None:
        if not self.redo_stack:
            return None
        self.undo_stack.append(current)
        return self.redo_stack.pop()

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
