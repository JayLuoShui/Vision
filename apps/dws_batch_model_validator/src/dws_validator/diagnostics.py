# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .runtime_paths import RuntimePaths


@dataclass
class DiagnoseResult:
    app_version: str
    python_version: str
    platform: str
    frozen: bool
    app_dir: str
    user_data_dir: str
    opencv_available: bool
    ultralytics_available: bool
    openvino_available: bool
    openvino_version: str
    torch_available: bool
    cuda_available: bool
    gpu_name: str
    numpy_available: bool
    pandas_available: bool
    yaml_available: bool
    default_model_exists: bool
    recommended_device: str
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def _module_available(name: str) -> tuple[bool, str]:
    try:
        if importlib.util.find_spec(name) is None:
            return False, f"{name} 未安装"
        return True, ""
    except Exception as exc:  # noqa: BLE001
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


def diagnose_environment(model_path: str | Path | None = None) -> DiagnoseResult:
    paths = RuntimePaths()
    paths.ensure_user_dirs()
    errors: list[str] = []
    modules: dict[str, bool] = {}
    for name in ["cv2", "ultralytics", "openvino", "torch", "numpy", "pandas", "yaml"]:
        ok, err = _module_available(name)
        modules[name] = ok
        if err and name in {"cv2", "numpy", "pandas", "yaml"}:
            errors.append(err)

    cuda_available = False
    gpu_name = _nvidia_gpu_name()
    openvino_version = ""
    if modules["openvino"]:
        try:
            import openvino

            openvino_version = str(getattr(openvino, "__version__", ""))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"OpenVINO 检查失败：{exc}")

    if modules["torch"]:
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
            if cuda_available:
                gpu_name = str(torch.cuda.get_device_name(0))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"torch 检查失败：{exc}")

    model = Path(model_path) if model_path else paths.default_model_dir / "yolo26s-seg.pt"
    return DiagnoseResult(
        app_version=__version__,
        python_version=sys.version.replace("\n", " "),
        platform=platform.platform(),
        frozen=bool(getattr(sys, "frozen", False)),
        app_dir=str(paths.app_dir),
        user_data_dir=str(paths.user_data_dir),
        opencv_available=modules["cv2"],
        ultralytics_available=modules["ultralytics"],
        openvino_available=modules["openvino"],
        openvino_version=openvino_version,
        torch_available=modules["torch"],
        cuda_available=cuda_available,
        gpu_name=gpu_name,
        numpy_available=modules["numpy"],
        pandas_available=modules["pandas"],
        yaml_available=modules["yaml"],
        default_model_exists=model.exists(),
        recommended_device="0" if cuda_available else "cpu",
        errors=errors,
    )
