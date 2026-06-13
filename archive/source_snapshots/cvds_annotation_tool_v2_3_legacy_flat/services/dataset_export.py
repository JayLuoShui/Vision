from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExportResult:
    output_dir: Path
    train_count: int
    val_count: int
    zip_path: Path | None = None


def _images(root: Path) -> list[Path]:
    suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return sorted([path for path in (root / "images" / "train").rglob("*") if path.suffix.lower() in suffixes])


def _copy_item(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def export_dataset(
    output_root: Path,
    export_to: Path,
    val_ratio: float = 0.2,
    include_empty: bool = True,
    make_zip: bool = False,
) -> ExportResult:
    output_root = Path(output_root)
    export_to = Path(export_to)
    if export_to.exists():
        shutil.rmtree(export_to)
    export_to.mkdir(parents=True, exist_ok=True)
    candidates = []
    for image_path in _images(output_root):
        label_path = output_root / "labels" / "train" / f"{image_path.stem}.txt"
        if not include_empty and (not label_path.exists() or not label_path.read_text(encoding="utf-8", errors="ignore").strip()):
            continue
        candidates.append(image_path)
    val_count = int(round(len(candidates) * val_ratio))
    val_items = set(candidates[-val_count:]) if val_count else set()
    train_count = 0
    actual_val_count = 0
    for image_path in candidates:
        split = "val" if image_path in val_items else "train"
        if split == "train":
            train_count += 1
        else:
            actual_val_count += 1
        _copy_item(image_path, export_to / "images" / split / image_path.name)
        _copy_item(output_root / "labels" / "train" / f"{image_path.stem}.txt", export_to / "labels" / split / f"{image_path.stem}.txt")
        _copy_item(output_root / "defects" / "train" / f"{image_path.stem}.json", export_to / "defects" / split / f"{image_path.stem}.json")
    data_yaml = output_root / "data.yaml"
    if data_yaml.exists():
        _copy_item(data_yaml, export_to / "data.yaml")
    else:
        (export_to / "data.yaml").write_text("path: .\ntrain: images/train\nval: images/val\nnames:\n  0: parcel\n", encoding="utf-8")
    zip_path = None
    if make_zip:
        zip_path = export_to.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in export_to.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(export_to.parent))
    return ExportResult(export_to, train_count, actual_val_count, zip_path)
