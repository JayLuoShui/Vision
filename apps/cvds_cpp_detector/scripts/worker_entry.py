from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


GPU_UNAVAILABLE_MESSAGE = "检测到 NVIDIA 显卡/驱动，但当前运行包内 PyTorch 未启用 CUDA，请使用 CUDA 版运行包或改用 CPU。"


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def import_status(module_name: str) -> tuple[bool, str]:
    try:
        __import__(module_name)
    except Exception as exc:
        return False, str(exc)
    return True, ""


def query_nvidia_smi() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except FileNotFoundError:
        return {"available": False, "gpu_name": "", "driver_version": "", "error": "未找到 nvidia-smi。"}
    except Exception as exc:
        return {"available": False, "gpu_name": "", "driver_version": "", "error": str(exc)}

    if completed.returncode != 0:
        return {
            "available": False,
            "gpu_name": "",
            "driver_version": "",
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }

    first_line = completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else ""
    parts = [part.strip() for part in first_line.split(",", 1)]
    return {
        "available": bool(first_line),
        "gpu_name": parts[0] if parts else "",
        "driver_version": parts[1] if len(parts) > 1 else "",
        "error": "",
    }


def collect_runtime_diagnostics() -> dict[str, Any]:
    errors: list[str] = []
    nvidia = query_nvidia_smi()
    torch_available = False
    cuda_available = False
    gpu_name = ""
    torch_version = ""
    torch_cuda_version = ""

    try:
        import torch

        torch_available = True
        torch_version = str(torch.__version__)
        torch_cuda_version = str(torch.version.cuda or "")
        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            gpu_name = str(torch.cuda.get_device_name(0))
    except Exception as exc:
        errors.append(f"torch: {exc}")

    ultralytics_available, ultralytics_error = import_status("ultralytics")
    if not ultralytics_available:
        errors.append(f"ultralytics: {ultralytics_error}")

    opencv_available, opencv_error = import_status("cv2")
    if not opencv_available:
        errors.append(f"opencv: {opencv_error}")

    numpy_available, numpy_error = import_status("numpy")
    if not numpy_available:
        errors.append(f"numpy: {numpy_error}")

    cuda_issue = ""
    if not cuda_available:
        if nvidia["available"] and torch_available:
            if torch_cuda_version:
                cuda_issue = "检测到 NVIDIA 显卡/驱动，但 PyTorch CUDA 初始化失败，请检查驱动与 CUDA 版 PyTorch 是否匹配。"
            else:
                cuda_issue = GPU_UNAVAILABLE_MESSAGE
        elif not nvidia["available"]:
            cuda_issue = "未检测到 NVIDIA 驱动或 nvidia-smi，请先安装 NVIDIA 驱动。"

    return {
        "type": "diagnose",
        "python_runtime": True,
        "torch_available": torch_available,
        "torch_version": torch_version,
        "torch_cuda_version": torch_cuda_version,
        "cuda_available": cuda_available,
        "ultralytics_available": ultralytics_available,
        "opencv_available": opencv_available,
        "numpy_available": numpy_available,
        "nvidia_driver_available": bool(nvidia["available"]),
        "nvidia_gpu_name": nvidia["gpu_name"],
        "nvidia_driver_version": nvidia["driver_version"],
        "nvidia_smi_error": nvidia["error"],
        "gpu_name": gpu_name or nvidia["gpu_name"],
        "cuda_issue": cuda_issue,
        "recommend_device": "0" if cuda_available else "cpu",
        "errors": errors,
    }


def diagnose() -> int:
    diagnostics = collect_runtime_diagnostics()
    emit(diagnostics)
    required_ok = (
        diagnostics["torch_available"]
        and diagnostics["ultralytics_available"]
        and diagnostics["opencv_available"]
        and diagnostics["numpy_available"]
    )
    return 0 if required_ok else 1


def torch_cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def gpu_unavailable_message() -> str:
    diagnostics = collect_runtime_diagnostics()
    issue = str(diagnostics.get("cuda_issue") or "").strip()
    return issue or GPU_UNAVAILABLE_MESSAGE


def normalize_detect_device(value: str) -> str:
    device = (value or "auto").strip().lower()
    if device in {"auto", ""}:
        return "0" if torch_cuda_available() else "cpu"
    if device in {"cpu", "-1"}:
        return "cpu"
    if not torch_cuda_available():
        return "cpu"
    return value.strip()


def ensure_detect_inputs(args: argparse.Namespace) -> None:
    if not Path(args.weights).exists():
        raise FileNotFoundError(f"找不到模型：{args.weights}")
    if args.tracker and not Path(args.tracker).exists():
        raise FileNotFoundError(f"找不到 tracker 配置：{args.tracker}")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    probe = output_dir / ".cvds_worker_write_test.tmp"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)


def detect(args: argparse.Namespace) -> int:
    try:
        ensure_detect_inputs(args)
        requested_device = args.device
        args.device = normalize_detect_device(args.device)
    except Exception as exc:
        emit({"type": "error", "message": str(exc)})
        return 2

    if str(requested_device).strip().lower() not in {"", "auto", "cpu", "-1"} and args.device == "cpu":
        emit({"type": "status", "message": gpu_unavailable_message() + " 已自动切换 CPU。", "device": "cpu"})

    import pt_video_flow_monitor

    argv = [
        "pt_video_flow_monitor.py",
        "--weights",
        args.weights,
        "--source",
        args.source,
        "--output-dir",
        args.output_dir,
        "--preview-path",
        args.preview_path,
        "--roi",
        args.roi,
        "--conf",
        str(args.conf),
        "--iou",
        str(args.iou),
        "--imgsz",
        str(args.imgsz),
        "--device",
        args.device,
        "--class-id",
        str(args.class_id),
        "--tracker",
        args.tracker,
        "--preview-fps",
        str(args.preview_fps),
        "--jam-seconds",
        str(args.jam_seconds),
        "--jam-signal-path",
        args.jam_signal_path,
    ]
    if args.max_frames > 0:
        argv.extend(["--max-frames", str(args.max_frames)])
    if args.detect_roi:
        argv.extend(["--detect-roi", args.detect_roi])
    sys.argv = argv
    try:
        pt_video_flow_monitor.main()
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        emit({"type": "error", "message": str(exc)})
        return 1
    return 0


def inspect_model(args: argparse.Namespace) -> int:
    import inspect_model_metadata

    sys.argv = ["inspect_model_metadata.py", "--model", args.model]
    try:
        return int(inspect_model_metadata.main())
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        emit({"type": "error", "message": str(exc)})
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CVDS 检测 worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser("detect", help="执行视频检测")
    detect_parser.add_argument("--weights", required=True)
    detect_parser.add_argument("--source", required=True)
    detect_parser.add_argument("--output-dir", required=True)
    detect_parser.add_argument("--preview-path", required=True)
    detect_parser.add_argument("--roi", required=True)
    detect_parser.add_argument("--detect-roi", default=None)
    detect_parser.add_argument("--conf", type=float, default=0.25)
    detect_parser.add_argument("--iou", type=float, default=0.45)
    detect_parser.add_argument("--imgsz", type=int, default=960)
    detect_parser.add_argument("--device", default="auto")
    detect_parser.add_argument("--class-id", type=int, default=-1)
    detect_parser.add_argument("--tracker", required=True)
    detect_parser.add_argument("--preview-fps", type=int, default=30)
    detect_parser.add_argument("--jam-seconds", type=int, default=5)
    detect_parser.add_argument("--jam-signal-path", required=True)
    detect_parser.add_argument("--max-frames", type=int, default=0)
    detect_parser.set_defaults(func=detect)

    inspect_parser = subparsers.add_parser("inspect-model", help="读取模型类别")
    inspect_parser.add_argument("--model", required=True)
    inspect_parser.set_defaults(func=inspect_model)

    diagnose_parser = subparsers.add_parser("diagnose", help="检查 worker 运行环境")
    diagnose_parser.set_defaults(func=lambda _args: diagnose())
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
