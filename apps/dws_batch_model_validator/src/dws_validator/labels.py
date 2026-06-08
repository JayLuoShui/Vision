# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Optional


def label_path_for_image(image_path: Path, labels_dir: Path) -> Path:
    return labels_dir / f"{image_path.stem}.txt"


def count_yolo_instances(label_path: Path) -> Optional[int]:
    """Count valid rows in a YOLO txt label file.

    For this DWS counting task, each valid non-empty row is one parcel instance.
    If label file does not exist, return None so the image can still be inferred
    but excluded from metrics.
    """
    if not label_path.exists():
        return None

    count = 0
    with label_path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) < 5:
                continue
            try:
                class_id = int(float(parts[0]))
                coords = [float(x) for x in parts[1:]]
            except ValueError:
                continue
            if class_id < 0:
                continue
            if len(coords) >= 4:
                count += 1
    return count
