from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="读取 PT 或 ONNX 模型中的类别信息")
    parser.add_argument("--model", required=True, help="模型路径，支持 .pt 和 .onnx")
    return parser.parse_args()


def normalize_names(raw_names: object) -> list[str]:
    if isinstance(raw_names, dict):
        return [str(raw_names[key]) for key in sorted(raw_names)]
    if isinstance(raw_names, list):
        return [str(item) for item in raw_names]
    if isinstance(raw_names, str) and raw_names.strip():
        parsed = ast.literal_eval(raw_names)
        return normalize_names(parsed)
    return []


def inspect_pt(model_path: Path) -> dict[str, object]:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    names = getattr(model, "names", {}) or {}
    task = getattr(model, "task", "") or getattr(getattr(model, "model", None), "task", "")
    return {
        "format": "pt",
        "task": str(task or "detect"),
        "class_names": normalize_names(names),
    }


def inspect_onnx(model_path: Path) -> dict[str, object]:
    import onnx

    model = onnx.load(str(model_path))
    metadata_props = {item.key: item.value for item in model.metadata_props}
    names = normalize_names(metadata_props.get("names", ""))
    task = str(metadata_props.get("task", "detect"))
    return {
        "format": "onnx",
        "task": task,
        "class_names": names,
        "metadata_props": metadata_props,
    }


def main() -> int:
    args = parse_args()
    model_path = Path(args.model).resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"模型不存在：{model_path}")

    suffix = model_path.suffix.lower()
    if suffix == ".pt":
        result = inspect_pt(model_path)
    elif suffix == ".onnx":
        result = inspect_onnx(model_path)
    else:
        raise ValueError("当前只支持读取 .pt 或 .onnx 模型")

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
