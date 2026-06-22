import argparse
import json
from pathlib import Path

import torch
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "datasets" / "cvds_annotation_yolo_labeled_20260508" / "data.yaml"
DEFAULT_MODEL = ROOT / "weights" / "pretrained" / "yolo26s.pt"
DEFAULT_PROJECT = ROOT / "runs" / "package_train"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="训练真实交叉带人工标注 YOLO26s 包裹检测模型")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="YOLO 数据集 data.yaml")
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="YOLO26s 初始权重")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT), help="训练输出目录")
    parser.add_argument("--name", default="yolo26s_cvds_manual_832_adamw", help="实验名称")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--imgsz", type=int, default=832)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--device", default="0")
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def hardware_profile(device: str) -> dict:
    has_cuda = torch.cuda.is_available() and device != "cpu"
    profile = {"has_cuda": has_cuda, "device": device}
    if has_cuda:
        profile["gpu_name"] = torch.cuda.get_device_name(0)
        profile["gpu_memory_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
    return profile


def main() -> int:
    args = parse_args()
    profile = hardware_profile(args.device)
    model = YOLO(args.model)

    train_args = {
        "data": args.data,
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "workers": args.workers,
        "device": args.device,
        "project": args.project,
        "name": args.name,
        "exist_ok": True,
        "pretrained": True,
        "optimizer": "AdamW",
        "lr0": 0.0012,
        "lrf": 0.02,
        "weight_decay": 0.0007,
        "warmup_epochs": 4.0,
        "warmup_momentum": 0.8,
        "cos_lr": True,
        "patience": args.patience,
        "close_mosaic": 12,
        "mosaic": 0.35,
        "mixup": 0.0,
        "copy_paste": 0.0,
        "hsv_h": 0.005,
        "hsv_s": 0.25,
        "hsv_v": 0.20,
        "degrees": 1.0,
        "translate": 0.04,
        "scale": 0.25,
        "shear": 0.0,
        "perspective": 0.0,
        "fliplr": 0.5,
        "flipud": 0.0,
        "cache": False,
        "multi_scale": 0.0,
        "plots": True,
        "val": True,
        "save": True,
        "save_period": 10,
        "seed": 20260508,
        "deterministic": True,
        "resume": args.resume,
    }

    print("TRAIN_PROFILE=" + json.dumps({"hardware": profile, "train_args": train_args}, ensure_ascii=False))
    result = model.train(**train_args)
    save_dir = Path(result.save_dir)
    best = save_dir / "weights" / "best.pt"
    last = save_dir / "weights" / "last.pt"

    val_metrics = model.val(data=args.data, split="val", imgsz=args.imgsz, batch=args.batch, device=args.device, workers=args.workers)
    test_metrics = model.val(data=args.data, split="test", imgsz=args.imgsz, batch=args.batch, device=args.device, workers=args.workers)

    summary = {
        "save_dir": str(save_dir),
        "best": str(best),
        "last": str(last),
        "hardware": profile,
        "train_args": train_args,
        "val_results": getattr(val_metrics, "results_dict", {}),
        "test_results": getattr(test_metrics, "results_dict", {}),
    }
    (save_dir / "cvds_yolo26s_manual_train_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("TRAIN_DONE=" + json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
