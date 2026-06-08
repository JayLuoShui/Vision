from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将 Ultralytics .pt 权重转换为 ONNX")
    parser.add_argument("--weights", required=True, help="输入 .pt 权重路径")
    parser.add_argument("--output", required=True, help="输出 .onnx 路径")
    parser.add_argument("--imgsz", type=int, default=960, help="导出输入尺寸")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset")
    parser.add_argument("--device", default="cpu", help="导出设备，默认 cpu")
    parser.add_argument("--dynamic", dest="dynamic", action="store_true", default=True, help="导出动态输入尺寸，默认开启")
    parser.add_argument("--static", dest="dynamic", action="store_false", help="关闭动态输入尺寸")
    parser.add_argument("--simplify", action="store_true", help="启用 onnxsim 简化")
    return parser.parse_args()


def resolve_output_path(weights: Path, output_value: str) -> Path:
    output = Path(output_value).expanduser()
    if output.suffix.lower() == ".onnx":
        return output.resolve()
    return (output / f"{weights.stem}.onnx").resolve()


def main() -> int:
    args = parse_args()
    weights = Path(args.weights).resolve()
    output = resolve_output_path(weights, args.output)
    if not weights.exists():
        raise FileNotFoundError(f"权重不存在：{weights}")

    from ultralytics import YOLO

    output.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    exported = model.export(
        format="onnx",
        imgsz=args.imgsz,
        opset=args.opset,
        simplify=args.simplify,
        dynamic=args.dynamic,
        device=args.device,
        end2end=True,
    )
    exported_path = Path(str(exported)).resolve()
    if exported_path != output:
        shutil.copy2(exported_path, output)
    print(f"ONNX 已输出：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
