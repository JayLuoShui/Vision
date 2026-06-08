import argparse
import json
from pathlib import Path

import torch
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "datasets" / "cvds_package_yolo26_crossbelt" / "data.yaml"
DEFAULT_MODEL = ROOT / "yolo26n.pt"
DEFAULT_PROJECT = ROOT / "runs" / "package_train"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="训练 CVDS 包裹检测 YOLO26n 模型")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="YOLO26 数据集 data.yaml")
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="YOLO26n 初始权重")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT), help="训练输出目录")
    parser.add_argument("--name", default="yolo26n_cvds_package", help="实验名称")
    parser.add_argument("--epochs", type=int, default=None, help="训练轮数；不填则按设备自动选择")
    parser.add_argument("--imgsz", type=int, default=None, help="输入尺寸；不填则按设备自动选择")
    parser.add_argument("--batch", type=int, default=None, help="批大小；不填则按设备自动选择")
    parser.add_argument("--workers", type=int, default=0, help="Windows 下默认 0，避免多进程读图问题")
    parser.add_argument("--device", default=None, help="训练设备，例如 0 或 cpu；不填自动选择")
    parser.add_argument("--fraction", type=float, default=None, help="训练集采样比例；CPU 默认 0.2，GPU 默认 1.0")
    parser.add_argument("--patience", type=int, default=None, help="早停轮数；不填则按设备自动选择")
    parser.add_argument("--multi-scale", type=float, default=None, help="多尺度训练范围；不填则按设备自动选择")
    parser.add_argument("--resume", action="store_true", help="从最近训练继续")
    return parser.parse_args()


def auto_profile(args: argparse.Namespace) -> dict:
    has_cuda = torch.cuda.is_available()
    device = args.device if args.device is not None else ("0" if has_cuda else "cpu")
    gpu_memory_gb = 0.0
    if has_cuda:
        gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    if has_cuda and gpu_memory_gb < 7:
        default_batch = 4
    elif has_cuda:
        default_batch = 16
    else:
        default_batch = 8
    return {
        "device": device,
        "epochs": args.epochs if args.epochs is not None else (80 if has_cuda else 8),
        "imgsz": args.imgsz if args.imgsz is not None else (960 if has_cuda else 320),
        "batch": args.batch if args.batch is not None else default_batch,
        "fraction": args.fraction if args.fraction is not None else (1.0 if has_cuda else 0.2),
        "patience": args.patience if args.patience is not None else (20 if has_cuda else 5),
        "multi_scale": args.multi_scale if args.multi_scale is not None else (0.35 if has_cuda else 0.0),
        "has_cuda": has_cuda,
        "gpu_memory_gb": round(gpu_memory_gb, 2),
    }


def train() -> None:
    args = parse_args()
    profile = auto_profile(args)
    model = YOLO(args.model)

    train_args = {
        "data": args.data,
        "epochs": profile["epochs"],
        "imgsz": profile["imgsz"],
        "batch": profile["batch"],
        "workers": args.workers,
        "device": profile["device"],
        "fraction": profile["fraction"],
        "patience": profile["patience"],
        "project": args.project,
        "name": args.name,
        "exist_ok": True,
        "pretrained": True,
        "optimizer": "AdamW",
        "lr0": 0.002,
        "lrf": 0.01,
        "weight_decay": 0.0005,
        "warmup_epochs": 3.0,
        "cos_lr": True,
        "close_mosaic": 10,
        "mosaic": 1.0,
        "mixup": 0.0,
        "copy_paste": 0.0,
        "hsv_h": 0.01,
        "hsv_s": 0.35,
        "hsv_v": 0.25,
        "degrees": 2.0,
        "translate": 0.08,
        "scale": 0.70,
        "shear": 0.0,
        "perspective": 0.0,
        "fliplr": 0.5,
        "flipud": 0.0,
        "cache": False,
        "multi_scale": profile["multi_scale"],
        "plots": True,
        "val": True,
        "save": True,
        "seed": 20260506,
        "deterministic": True,
        "resume": args.resume,
    }

    print("TRAIN_PROFILE=" + json.dumps(profile, ensure_ascii=False))
    result = model.train(**train_args)
    save_dir = Path(result.save_dir)
    best = save_dir / "weights" / "best.pt"
    last = save_dir / "weights" / "last.pt"
    summary = {
        "save_dir": str(save_dir),
        "best": str(best),
        "last": str(last),
        "profile": profile,
        "train_args": train_args,
    }
    (save_dir / "cvds_train_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("TRAIN_DONE=" + json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    train()
