import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psutil


@dataclass(frozen=True)
class WeightFileStatus:
    path: Path
    exists: bool
    size_bytes: int
    modified_at: datetime | None


@dataclass(frozen=True)
class TrainingProcessStatus:
    running: bool
    process_id: int | None
    command_line: str


@dataclass(frozen=True)
class TrainingSnapshot:
    run_dir: Path
    args: dict[str, str]
    total_epochs: int
    finished_epochs: int
    progress_percent: float
    latest_metrics: dict[str, float]
    best_map50: float
    best_map5095: float
    weights: dict[str, WeightFileStatus]
    process: TrainingProcessStatus


def find_latest_training_run(project_dir: Path) -> Path | None:
    project_dir = Path(project_dir)
    if not project_dir.exists():
        return None
    candidates = [
        path
        for path in project_dir.iterdir()
        if path.is_dir() and ((path / "results.csv").exists() or (path / "args.yaml").exists())
    ]
    if not candidates:
        return None
    return max(candidates, key=_run_modified_at)


def _run_modified_at(run_dir: Path) -> float:
    paths = [
        run_dir / "results.csv",
        run_dir / "args.yaml",
        run_dir / "weights" / "last.pt",
        run_dir / "weights" / "best.pt",
    ]
    times = [path.stat().st_mtime for path in paths if path.exists()]
    return max(times) if times else run_dir.stat().st_mtime


def read_training_snapshot(run_dir: Path) -> TrainingSnapshot:
    run_dir = Path(run_dir)
    args = read_args(run_dir / "args.yaml")
    rows = read_results(run_dir / "results.csv")
    total_epochs = int(float(args.get("epochs", "0") or 0))
    latest = rows[-1] if rows else {}
    latest_epoch = int(latest.get("epoch", -1)) if latest else -1
    finished_epochs = latest_epoch + 1 if latest_epoch >= 0 else 0
    progress_percent = round((finished_epochs / total_epochs * 100), 2) if total_epochs > 0 else 0.0
    best_map50 = max((row.get("metrics/mAP50(B)", 0.0) for row in rows), default=0.0)
    best_map5095 = max((row.get("metrics/mAP50-95(B)", 0.0) for row in rows), default=0.0)
    weights = {
        "best.pt": read_weight_status(run_dir / "weights" / "best.pt"),
        "last.pt": read_weight_status(run_dir / "weights" / "last.pt"),
    }
    return TrainingSnapshot(
        run_dir=run_dir,
        args=args,
        total_epochs=total_epochs,
        finished_epochs=finished_epochs,
        progress_percent=progress_percent,
        latest_metrics=latest,
        best_map50=best_map50,
        best_map5095=best_map5095,
        weights=weights,
        process=find_training_process(run_dir),
    )


def read_args(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    args: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        args[key.strip()] = value.strip().strip("'\"")
    return args


def read_results(path: Path) -> list[dict[str, float]]:
    if not path.exists():
        return []
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            parsed: dict[str, float] = {}
            for key, value in row.items():
                if key is None or value in (None, ""):
                    continue
                parsed[key.strip()] = float(value)
            rows.append(parsed)
    return rows


def read_weight_status(path: Path) -> WeightFileStatus:
    if not path.exists():
        return WeightFileStatus(path=path, exists=False, size_bytes=0, modified_at=None)
    stat = path.stat()
    return WeightFileStatus(
        path=path,
        exists=True,
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime),
    )


def find_training_process(run_dir: Path) -> TrainingProcessStatus:
    lower_run_dir = str(run_dir).lower()
    training_processes = []
    for process in _iter_processes():
        command_line = _join_command_line(process.get("cmdline") or [])
        if not _looks_like_training_process(command_line):
            continue
        training_processes.append((int(process["pid"]), command_line))
        lower_command = command_line.lower()
        if lower_run_dir in lower_command or run_dir.name.lower() in lower_command:
            return TrainingProcessStatus(True, int(process["pid"]), command_line)
    if training_processes:
        pid, command_line = training_processes[0]
        return TrainingProcessStatus(True, pid, command_line)
    return TrainingProcessStatus(False, None, "")


def _iter_processes() -> list[dict]:
    processes = []
    for process in psutil.process_iter(["pid", "cmdline"]):
        try:
            processes.append(process.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


def _looks_like_training_process(command_line: str) -> bool:
    lower_command = command_line.lower()
    return (
        "train_yolo26" in lower_command
        or "ultralytics" in lower_command
        or "model.train" in lower_command
    )


def _join_command_line(parts: list[str]) -> str:
    return " ".join(str(part) for part in parts if part)
