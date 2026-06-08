from __future__ import annotations

import importlib.util
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class DiagnoseResult:
    python_runtime: str
    frozen: bool
    platform: str
    pyside6_available: bool
    ultralytics_available: bool
    torch_available: bool
    cuda_available: bool
    gpu_name: str
    cv2_available: bool
    numpy_available: bool
    yaml_available: bool
    sam_available: bool
    sam_error: str
    yolo_weights_exists: bool
    sam_weights_ready: bool
    recommend_device: str
    errors: list[str]
    suggestions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def _module_available(name: str) -> tuple[bool, str]:
    try:
        if importlib.util.find_spec(name) is None:
            return False, f"{name} 未安装"
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _nvidia_gpu_name() -> str:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip().splitlines()[0].strip() if result.stdout.strip() else ""


def check_sam_available() -> tuple[bool, str]:
    if importlib.util.find_spec("torch") is None:
        return False, "未安装 torch，SAM 半自动分割不可用。"
    if importlib.util.find_spec("ultralytics") is None:
        return False, "未安装 ultralytics，SAM 半自动分割不可用。"
    first_error = ""
    try:
        from ultralytics import SAM  # noqa: F401

        return True, ""
    except Exception as exc:  # noqa: BLE001
        first_error = str(exc)
    try:
        from ultralytics.models.sam import SAM  # noqa: F401

        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"无法从 ultralytics 导入 SAM：{first_error}; {exc}"


def diagnose_environment(yolo_weights: str | Path | None = None, sam_weights: str | Path | None = None) -> DiagnoseResult:
    errors: list[str] = []
    suggestions: list[str] = []
    module_status = {}
    for name in ["PySide6", "ultralytics", "torch", "cv2", "numpy", "yaml"]:
        ok, error = _module_available(name)
        module_status[name] = ok
        if error and name in {"PySide6", "cv2", "numpy", "yaml"}:
            errors.append(error)

    cuda_available = False
    gpu_name = _nvidia_gpu_name()
    if module_status["torch"]:
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
            if cuda_available:
                gpu_name = str(torch.cuda.get_device_name(0))
        except Exception as exc:
            errors.append(f"torch 检查失败：{exc}")

    sam_available, sam_error = check_sam_available()
    if not module_status["ultralytics"] or not module_status["torch"]:
        suggestions.append("当前发布包未包含 AI 自动标注环境，基础手工标注功能仍可正常使用。")
    if not sam_available:
        suggestions.append("当前发布包未包含 SAM 半自动分割环境，基础手工标注功能仍可正常使用。")
    if module_status["torch"] and not cuda_available:
        suggestions.append("CUDA 不可用时会使用 CPU；如需 GPU，请安装匹配的 GPU 运行环境。")

    yolo_path = Path(yolo_weights) if yolo_weights else None
    yolo_exists = bool(yolo_path and yolo_path.exists())
    sam_text = str(sam_weights or "").strip()
    official_sam = sam_text in {"mobile_sam.pt", "sam2.1_t.pt", "sam2.1_s.pt", "sam_b.pt", "sam_l.pt", "sam_h.pt"}
    sam_ready = bool((sam_text and Path(sam_text).exists()) or official_sam)
    return DiagnoseResult(
        python_runtime=sys.executable,
        frozen=bool(getattr(sys, "frozen", False)),
        platform=platform.platform(),
        pyside6_available=module_status["PySide6"],
        ultralytics_available=module_status["ultralytics"],
        torch_available=module_status["torch"],
        cuda_available=cuda_available,
        gpu_name=gpu_name,
        cv2_available=module_status["cv2"],
        numpy_available=module_status["numpy"],
        yaml_available=module_status["yaml"],
        sam_available=sam_available,
        sam_error=sam_error,
        yolo_weights_exists=yolo_exists,
        sam_weights_ready=sam_ready,
        recommend_device="0" if cuda_available else "cpu",
        errors=errors,
        suggestions=suggestions,
    )
