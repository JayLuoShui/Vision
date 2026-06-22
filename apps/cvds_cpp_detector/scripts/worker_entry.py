from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

GPU_UNAVAILABLE_MESSAGE = "检测到 NVIDIA 显卡/驱动，但当前运行包内 PyTorch 未启用 CUDA，请使用 CUDA 版运行包或改用 CPU。"
PT_DEVICE_CHOICES = ("auto", "cpu", "0")
OPENVINO_DEVICE_MAP = {
    "auto": "AUTO",
    "intel:cpu": "CPU",
    "intel:gpu": "GPU",
    "intel:npu": "NPU",
}


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def metadata_tools():
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    import inspect_model_metadata

    return inspect_model_metadata


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

    pillow_available, pillow_error = import_status("PIL")
    if not pillow_available:
        errors.append(f"pillow: {pillow_error}")

    numpy_available, numpy_error = import_status("numpy")
    if not numpy_available:
        errors.append(f"numpy: {numpy_error}")

    onnx_available, onnx_error = import_status("onnx")
    if not onnx_available:
        errors.append(f"onnx: {onnx_error}")

    onnxruntime_available, onnxruntime_error = import_status("onnxruntime")
    if not onnxruntime_available:
        errors.append(f"onnxruntime: {onnxruntime_error}")

    openvino_available, openvino_error = import_status("openvino")
    if not openvino_available:
        errors.append(f"openvino: {openvino_error}")

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
        "pillow_available": pillow_available,
        "numpy_available": numpy_available,
        "onnx_available": onnx_available,
        "onnxruntime_available": onnxruntime_available,
        "openvino_available": openvino_available,
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
        and diagnostics["pillow_available"]
        and diagnostics["numpy_available"]
        and diagnostics["onnx_available"]
        and diagnostics["onnxruntime_available"]
        and diagnostics["openvino_available"]
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


def available_openvino_devices() -> set[str]:
    import openvino as ov

    core = ov.Core()
    return {str(device).strip().upper() for device in getattr(core, "available_devices", []) if str(device).strip()}


def normalize_detect_device(value: str, artifact: Any) -> str:
    requested = (value or "auto").strip().lower()
    if artifact.backend in {"pt", "onnx"}:
        if requested not in PT_DEVICE_CHOICES:
            raise ValueError(f"{artifact.backend} 仅支持设备：auto、cpu、0")
        if requested == "auto":
            return "0" if torch_cuda_available() else "cpu"
        if requested == "cpu":
            return "cpu"
        if not torch_cuda_available():
            raise RuntimeError(gpu_unavailable_message())
        return "0"

    if requested not in OPENVINO_DEVICE_MAP:
        raise ValueError("OpenVINO 仅支持设备：auto、intel:cpu、intel:gpu、intel:npu")
    available = available_openvino_devices()
    if not available:
        raise RuntimeError("未检测到可用的 OpenVINO 设备")
    normalized = OPENVINO_DEVICE_MAP[requested]
    if normalized != "AUTO" and normalized not in available:
        found = ", ".join(sorted(device.lower() for device in available))
        raise RuntimeError(f"OpenVINO 设备不可用：{requested}。当前可用：{found}")
    return requested


def ensure_detect_inputs(args: argparse.Namespace) -> Any:
    artifact = metadata_tools().resolve_model_artifact(args.model)
    if args.tracker and not Path(args.tracker).exists():
        raise FileNotFoundError(f"找不到 tracker 配置：{args.tracker}")
    if args.regions:
        if not Path(args.regions).exists():
            raise FileNotFoundError(f"找不到 regions.json：{args.regions}")
    elif not args.roi:
        raise ValueError("必须传入 --regions 或 --roi，不能留空")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    probe = output_dir / ".cvds_worker_write_test.tmp"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
    return artifact


def detect(args: argparse.Namespace) -> int:
    try:
        artifact = ensure_detect_inputs(args)
        args.device = normalize_detect_device(args.device, artifact)
    except Exception as exc:
        emit({"type": "error", "message": str(exc)})
        return 2

    argv = [
        "pt_video_flow_monitor.py",
        "--model",
        args.model,
        "--source",
        args.source,
        "--rtsp-transport",
        args.rtsp_transport,
        "--output-dir",
        args.output_dir,
        "--preview-path",
        args.preview_path,
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
    if args.regions:
        argv.extend(["--regions", args.regions])
    elif args.roi:
        argv.extend(["--roi", args.roi])
    if args.max_frames > 0:
        argv.extend(["--max-frames", str(args.max_frames)])
    if args.detect_roi:
        argv.extend(["--detect-roi", args.detect_roi])
    sys.argv = argv
    try:
        import pt_video_flow_monitor

        pt_video_flow_monitor.main()
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        emit({"type": "error", "message": str(exc)})
        return 1
    return 0


def inspect_model(args: argparse.Namespace) -> int:
    inspect_model_metadata = metadata_tools()

    sys.argv = ["inspect_model_metadata.py", "--model", args.model]
    try:
        return int(inspect_model_metadata.main())
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        emit({"type": "error", "message": str(exc)})
        return 1


def sanitize_source_for_log(source: str) -> str:
    parts = urlsplit(source)
    if not parts.scheme or "@" not in parts.netloc:
        return source
    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    username = parts.username or ""
    netloc = f"{username}@{hostname}{port}" if username else f"{hostname}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def open_probe_capture(source: str, rtsp_transport: str):
    import cv2

    normalized = source.strip().lower()
    if normalized.isdigit():
        return cv2.VideoCapture(int(source))
    if normalized.startswith("rtsp://"):
        import os

        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{rtsp_transport}"
        backend = getattr(cv2, "CAP_FFMPEG", None)
        params: list[int] = []
        if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
            params.extend([int(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC), 5000])
        if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
            params.extend([int(cv2.CAP_PROP_READ_TIMEOUT_MSEC), 5000])
        if backend is not None:
            if params:
                return cv2.VideoCapture(source, backend, params)
            return cv2.VideoCapture(source, backend)
    return cv2.VideoCapture(source)


def probe_source(args: argparse.Namespace) -> int:
    source = sanitize_source_for_log(args.source)
    capture = None
    try:
        capture = open_probe_capture(args.source, args.rtsp_transport)
        if not capture.isOpened():
            emit(
                {
                    "type": "probe",
                    "ok": False,
                    "source": source,
                    "transport": args.rtsp_transport,
                    "message": "无法打开视频源",
                }
            )
            return 1
        ok, _frame = capture.read()
        if not ok:
            emit(
                {
                    "type": "probe",
                    "ok": False,
                    "source": source,
                    "transport": args.rtsp_transport,
                    "message": "视频流读取失败",
                }
            )
            return 1
        emit(
            {
                "type": "probe",
                "ok": True,
                "source": source,
                "transport": args.rtsp_transport,
                "message": "连接成功",
            }
        )
        return 0
    except Exception as exc:
        emit(
            {
                "type": "probe",
                "ok": False,
                "source": source,
                "transport": args.rtsp_transport,
                "message": str(exc),
            }
        )
        return 1
    finally:
        if capture is not None:
            capture.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CVDS 检测 worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser("detect", help="执行视频检测")
    detect_parser.add_argument("--model", required=True)
    detect_parser.add_argument("--source", required=True)
    detect_parser.add_argument("--rtsp-transport", choices=["tcp", "udp"], default="tcp")
    detect_parser.add_argument("--output-dir", required=True)
    detect_parser.add_argument("--preview-path", required=True)
    detect_parser.add_argument("--roi", default=None)
    detect_parser.add_argument("--regions", default=None)
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

    probe_parser = subparsers.add_parser("probe-source", help="测试视频源连接")
    probe_parser.add_argument("--source", required=True)
    probe_parser.add_argument("--rtsp-transport", choices=["tcp", "udp"], default="tcp")
    probe_parser.set_defaults(func=probe_source)

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
