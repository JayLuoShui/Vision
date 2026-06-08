import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_DATA = Path("datasets/cvds_20260512_yolomask_bg_aug_20260513/data.yaml")
DEFAULT_PROJECT = Path("runs/segment_train")
DEFAULT_NAME = "yolo26s_seg_yolomask_bg_aug_960"


@dataclass(frozen=True)
class TrainingProfile:
    model: str
    imgsz: int
    batch: int
    workers: int
    epochs: int
    patience: int
    optimizer: str
    lr0: float
    cos_lr: bool
    amp: bool
    cache: bool
    plots: bool


def choose_training_profile(total_vram_mib: int) -> TrainingProfile:
    if total_vram_mib >= 5500:
        return TrainingProfile(
            model="yolo26s-seg.pt",
            imgsz=960,
            batch=2,
            workers=2,
            epochs=120,
            patience=25,
            optimizer="AdamW",
            lr0=0.003,
            cos_lr=True,
            amp=True,
            cache=False,
            plots=True,
        )
    raise RuntimeError("GPU 显存低于 5.5GB，不启动分割训练")


def detect_total_vram_mib() -> int:
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        raise RuntimeError("未找到 nvidia-smi，不能确认 GPU 显存")
    result = subprocess.run(
        [nvidia_smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    first_line = result.stdout.strip().splitlines()[0]
    return int(first_line.strip())


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def ensure_source_path(source_root: Path) -> None:
    source_text = str(source_root)
    if sys.path[0] != source_text:
        sys.path = [path for path in sys.path if Path(path).resolve() != source_root]
        sys.path.insert(0, source_text)


def train(args: argparse.Namespace) -> Path:
    data_path = resolve_path(args.data)
    project = resolve_path(args.project)
    if not data_path.exists():
        raise RuntimeError(f"训练数据不存在: {data_path}")

    total_vram_mib = detect_total_vram_mib()
    profile = choose_training_profile(total_vram_mib)
    epochs = args.epochs if args.epochs is not None else profile.epochs
    name = args.name or DEFAULT_NAME
    source_root = Path(args.source_root).resolve()

    os.environ["PYTHONPATH"] = str(source_root)
    os.environ["PYTHONIOENCODING"] = "utf-8"
    ensure_source_path(source_root)

    from ultralytics import YOLO

    model = YOLO(profile.model)
    results = model.train(
        data=str(data_path),
        epochs=epochs,
        imgsz=profile.imgsz,
        batch=profile.batch,
        device=0,
        workers=profile.workers,
        project=str(project),
        name=name,
        optimizer=profile.optimizer,
        lr0=profile.lr0,
        cos_lr=profile.cos_lr,
        patience=profile.patience,
        amp=profile.amp,
        cache=profile.cache,
        plots=profile.plots,
        exist_ok=args.exist_ok,
    )
    save_dir = Path(results.save_dir).resolve()
    report = {
        "source_root": source_root.as_posix(),
        "data": data_path.as_posix(),
        "total_vram_mib": total_vram_mib,
        "profile": asdict(profile),
        "epochs": epochs,
        "save_dir": save_dir.as_posix(),
    }
    (save_dir / "training_profile.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return save_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--source-root", default="ultralytics")
    parser.add_argument("--exist-ok", action="store_true")
    return parser.parse_args()


def main() -> int:
    save_dir = train(parse_args())
    print(save_dir.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
