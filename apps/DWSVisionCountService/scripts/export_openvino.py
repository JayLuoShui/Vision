from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True)
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--out", default="models")
    parser.add_argument("--int8", action="store_true")
    parser.add_argument("--data", default=None)
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.weights)
    kwargs = {
        "format": "openvino",
        "imgsz": args.imgsz,
        "batch": 1,
        "dynamic": False,
        "half": False,
        "int8": args.int8,
        "project": args.out,
    }
    if args.data:
        kwargs["data"] = args.data
    output = model.export(**kwargs)
    print(Path(output))


if __name__ == "__main__":
    main()
