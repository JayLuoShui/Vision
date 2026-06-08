# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
import traceback
from . import __version__
from .config import load_config
from .diagnostics import diagnose_environment
from .runner import run_batch


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DWS panoramic image batch validator for YOLO segmentation parcel counting."
    )
    parser.add_argument("--cli", action="store_true", help="Run command-line batch mode when packaged exe is used.")
    parser.add_argument("--version", action="store_true", help="Print version and exit.")
    parser.add_argument("--diagnose", action="store_true", help="Print JSON environment diagnostics and exit.")
    parser.add_argument("--config", default="configs/default.yaml", help="Path to YAML config.")
    parser.add_argument("--model", default=None, help="Path to .pt model or Ultralytics OpenVINO *_openvino_model directory/.xml.")
    parser.add_argument("--images", default=None, help="Image directory. Files are scanned non-recursively.")
    parser.add_argument("--labels", default=None, help="YOLO label directory. Missing txt means infer only, no metrics.")
    parser.add_argument("--output", default=None, help="Output base directory. Timestamp run dir is created inside it.")
    parser.add_argument(
        "--imgsz",
        nargs=2,
        type=int,
        metavar=("H", "W"),
        default=None,
        help="Inference size as height width, e.g. --imgsz 736 960.",
    )
    parser.add_argument("--device", default=None, help="auto / cpu / 0 / cuda:0")
    parser.add_argument("--low-conf", type=float, default=None, help="Low confidence threshold for suspect candidates.")
    parser.add_argument("--high-conf", type=float, default=None, help="High confidence threshold for confirmed parcels.")
    parser.add_argument("--iou", type=float, default=None, help="NMS IoU threshold.")
    parser.add_argument("--save-vis", action="store_true", help="Force save visualization images.")
    parser.add_argument("--no-save-vis", action="store_true", help="Disable visualization images.")
    parser.add_argument("--mock-delay-ms", type=float, default=None, help="Mock signal sending delay in ms.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.version:
            print(__version__)
            return 0
        if args.diagnose:
            print(diagnose_environment(args.model).to_json())
            return 0
        cfg = load_config(
            args.config,
            model=args.model,
            images=args.images,
            labels=args.labels,
            output=args.output,
            imgsz=args.imgsz,
            device=args.device,
            low_conf=args.low_conf,
            high_conf=args.high_conf,
            iou=args.iou,
            save_vis=True if args.save_vis else None,
            no_save_vis=args.no_save_vis,
            mock_delay_ms=args.mock_delay_ms,
        )
        summary = run_batch(cfg)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"错误：{exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 2
