from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path


class AtomicWriteError(OSError):
    pass


def backup_existing_file(path: Path, backups_root: Path, file_type: str = "file") -> Path | None:
    if not path.exists():
        return None
    day_dir = backups_root / datetime.now().strftime("%Y%m%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    backup_name = f"{path.stem}_{datetime.now().strftime('%H%M%S_%f')}_{file_type}{path.suffix}"
    target = day_dir / backup_name
    shutil.copy2(path, target)
    return target


def atomic_write_text(path: Path, payload: str, *, fail_before_replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if fail_before_replace:
            raise AtomicWriteError("模拟写入失败")
        os.replace(tmp_path, path)
    except Exception as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, AtomicWriteError):
            raise
        raise AtomicWriteError(str(exc)) from exc


def move_dataset_item_to_trash(image_path: Path, output_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    trash_root = output_root / ".trash" / timestamp
    image_target = trash_root / "images" / "train" / image_path.name
    image_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(image_path), str(image_target))
    for folder, suffix in [("labels", ".txt"), ("defects", ".json")]:
        source = output_root / folder / "train" / f"{image_path.stem}{suffix}"
        if source.exists():
            target = trash_root / folder / "train" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
    return trash_root
