from __future__ import annotations

import json
from pathlib import Path

from cvds_annotation_tool.constants import DEFECT_META_VERSION
from cvds_annotation_tool.models.defect import DefectAnnotation
from cvds_annotation_tool.services.backup_service import atomic_write_text, backup_existing_file


def read_defects(path: Path, width: int, height: int) -> list[DefectAnnotation]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8", errors="ignore") or "{}")
    raw_defects = payload.get("defects") if isinstance(payload, dict) else []
    defects: list[DefectAnnotation] = []
    for item in raw_defects or []:
        if isinstance(item, dict):
            defect = DefectAnnotation.from_json(item, width, height)
            if defect is not None:
                defects.append(defect)
    return defects


def write_defects(
    path: Path,
    defects: list[DefectAnnotation],
    width: int,
    height: int,
    image_name: str,
    labels: list[str],
    backups_root: Path | None = None,
) -> None:
    valid_defects = [defect for defect in defects if defect.parent_index >= 0 and defect.is_valid()]
    if backups_root is not None:
        backup_existing_file(path, backups_root, "defect")
    if not valid_defects:
        path.unlink(missing_ok=True)
        return
    payload = {
        "version": DEFECT_META_VERSION,
        "image": image_name,
        "size": {"width": width, "height": height},
        "defects": [defect.to_json(width, height, labels) for defect in valid_defects],
    }
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
