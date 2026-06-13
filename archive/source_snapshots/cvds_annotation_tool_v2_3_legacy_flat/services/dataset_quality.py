from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from cvds_annotation_tool.constants import DEFECT_KINDS, DEFECT_SEVERITIES, DEFECT_TYPES


@dataclass
class QualityReport:
    output_root: str
    total_images: int = 0
    total_labels: int = 0
    empty_label_images: int = 0
    missing_labels: int = 0
    orphan_labels: int = 0
    invalid_defects: int = 0
    invalid_yolo_lines: int = 0
    out_of_bounds_coords: int = 0
    polygon_too_few_points: int = 0
    tiny_boxes: int = 0
    class_counts: dict[str, int] = field(default_factory=dict)
    defect_type_counts: dict[str, int] = field(default_factory=dict)
    defect_severity_counts: dict[str, int] = field(default_factory=dict)
    defect_kind_counts: dict[str, int] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    report_json: Path = Path()
    class_distribution_csv: Path = Path()

    def to_jsonable(self) -> dict:
        data = asdict(self)
        data["report_json"] = str(self.report_json)
        data["class_distribution_csv"] = str(self.class_distribution_csv)
        return data


def _image_files(root: Path) -> list[Path]:
    suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return sorted([path for path in (root / "images" / "train").rglob("*") if path.suffix.lower() in suffixes])


def _parse_label_line(line: str) -> tuple[int | None, list[float] | None]:
    parts = line.split()
    if len(parts) < 5:
        return None, None
    try:
        class_id = int(float(parts[0]))
        values = [float(item) for item in parts[1:]]
    except ValueError:
        return None, None
    return class_id, values


def audit_dataset(output_root: Path) -> QualityReport:
    output_root = Path(output_root)
    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = QualityReport(output_root=str(output_root))
    images = _image_files(output_root)
    image_stems = {path.stem for path in images}
    report.total_images = len(images)
    class_counts: Counter[str] = Counter()

    for image_path in images:
        label_path = output_root / "labels" / "train" / f"{image_path.stem}.txt"
        if not label_path.exists():
            report.missing_labels += 1
            continue
        lines = [line for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
        if not lines:
            report.empty_label_images += 1
        for line in lines:
            class_id, values = _parse_label_line(line)
            if class_id is None or values is None:
                report.invalid_yolo_lines += 1
                continue
            report.total_labels += 1
            class_counts[str(class_id)] += 1
            if any(value < 0 or value > 1 for value in values):
                report.out_of_bounds_coords += 1
            if len(values) == 4 and (values[2] < 0.001 or values[3] < 0.001):
                report.tiny_boxes += 1
            if len(values) != 4 and len(values) < 6:
                report.polygon_too_few_points += 1

    labels_dir = output_root / "labels" / "train"
    if labels_dir.exists():
        for label_path in labels_dir.glob("*.txt"):
            if label_path.stem not in image_stems:
                report.orphan_labels += 1

    defect_type_counts: Counter[str] = Counter()
    defect_severity_counts: Counter[str] = Counter()
    defect_kind_counts: Counter[str] = Counter()
    defects_dir = output_root / "defects" / "train"
    if defects_dir.exists():
        for defect_path in defects_dir.glob("*.json"):
            if defect_path.stem not in image_stems:
                report.invalid_defects += 1
                continue
            parent_count = len([line for line in (labels_dir / f"{defect_path.stem}.txt").read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]) if (labels_dir / f"{defect_path.stem}.txt").exists() else 0
            try:
                payload = json.loads(defect_path.read_text(encoding="utf-8", errors="ignore") or "{}")
            except json.JSONDecodeError:
                report.invalid_defects += 1
                continue
            for item in payload.get("defects") or []:
                parent_index = int(item.get("parent_index", -1)) if isinstance(item, dict) else -1
                kind = str(item.get("kind") or "polygon") if isinstance(item, dict) else "polygon"
                defect_type = str(item.get("type") or "other") if isinstance(item, dict) else "other"
                severity = str(item.get("severity") or "medium") if isinstance(item, dict) else "medium"
                if not (0 <= parent_index < parent_count):
                    report.invalid_defects += 1
                defect_type_counts[defect_type if defect_type in DEFECT_TYPES else "other"] += 1
                defect_severity_counts[severity if severity in DEFECT_SEVERITIES else "medium"] += 1
                defect_kind_counts[kind if kind in DEFECT_KINDS else "polygon"] += 1

    report.class_counts = dict(class_counts)
    report.defect_type_counts = dict(defect_type_counts)
    report.defect_severity_counts = dict(defect_severity_counts)
    report.defect_kind_counts = dict(defect_kind_counts)
    if report.missing_labels:
        report.suggestions.append("存在缺失 label 的图片，请生成空标签或补标。")
    if report.orphan_labels:
        report.suggestions.append("存在孤儿 label，请检查是否图片被移动或删除。")
    if report.invalid_yolo_lines or report.out_of_bounds_coords:
        report.suggestions.append("存在非法 YOLO 标签，请人工复核。")
    report.report_json = reports_dir / f"dataset_quality_{timestamp}.json"
    report.class_distribution_csv = reports_dir / "class_distribution.csv"
    report.report_json.write_text(json.dumps(report.to_jsonable(), ensure_ascii=False, indent=2), encoding="utf-8")
    with report.class_distribution_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["class_id", "count"])
        for class_id, count in sorted(report.class_counts.items(), key=lambda item: int(item[0])):
            writer.writerow([class_id, count])
    return report
