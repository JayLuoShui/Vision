from __future__ import annotations

from pathlib import Path

from cvds_annotation_tool.models.annotation import Annotation
from cvds_annotation_tool.services.backup_service import atomic_write_text, backup_existing_file


def read_yolo_annotations(path: Path, width: int, height: int) -> list[Annotation]:
    if not path.exists():
        return []
    annotations: list[Annotation] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        annotation = Annotation.from_yolo_line(line, width, height)
        if annotation is not None:
            annotations.append(annotation)
    return annotations


def write_yolo_annotations(
    path: Path,
    annotations: list[Annotation],
    width: int,
    height: int,
    backups_root: Path | None = None,
) -> None:
    lines = [line for item in annotations if (line := item.to_yolo_line(width, height)) is not None]
    if backups_root is not None:
        backup_existing_file(path, backups_root, "label")
    atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def ensure_empty_label(path: Path) -> None:
    if path.exists():
        return
    atomic_write_text(path, "")
