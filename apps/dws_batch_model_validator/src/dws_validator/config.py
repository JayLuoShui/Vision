# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from .runtime_paths import RuntimePaths


@dataclass
class RuntimeConfig:
    model_path: str
    images_dir: str
    labels_dir: str
    output_base_dir: str
    imgsz_h: int = 736
    imgsz_w: int = 960
    device: str = "auto"
    half: bool = False
    retina_masks: bool = True
    low_conf: float = 0.25
    high_conf: float = 0.55
    iou: float = 0.50
    multi_gt_min_count: int = 2
    save_vis: bool = True
    save_error_images: bool = True
    vis_all: bool = True
    mock_delay_ms: float = 0.0
    image_exts: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.image_exts is None:
            self.image_exts = [".jpg", ".jpeg", ".png", ".bmp"]
        self.image_exts = [x.lower() for x in self.image_exts]
        if not (0.0 <= self.low_conf <= 1.0):
            raise ValueError("low_conf must be between 0 and 1")
        if not (0.0 <= self.high_conf <= 1.0):
            raise ValueError("high_conf must be between 0 and 1")
        if self.low_conf > self.high_conf:
            raise ValueError("low_conf must be <= high_conf")


def _load_yaml(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_config_path(config_path: str | Path) -> Path:
    paths = RuntimePaths()
    value = Path(config_path)
    if value.is_absolute():
        return value
    cwd_path = (Path.cwd() / value).resolve()
    if cwd_path.exists():
        return cwd_path
    app_path = paths.resolve_app_path(value)
    if app_path.exists():
        return app_path
    return cwd_path


def _resolve_runtime_path(value: str | Path, *, cli_override: bool) -> str:
    paths = RuntimePaths()
    if cli_override:
        return str(paths.resolve_cwd_path(value))
    return str(paths.resolve_app_path(value))


def load_config(
    config_path: str | Path = "configs/default.yaml",
    *,
    model: Optional[str] = None,
    images: Optional[str] = None,
    labels: Optional[str] = None,
    output: Optional[str] = None,
    imgsz: Optional[List[int]] = None,
    device: Optional[str] = None,
    low_conf: Optional[float] = None,
    high_conf: Optional[float] = None,
    iou: Optional[float] = None,
    save_vis: Optional[bool] = None,
    no_save_vis: bool = False,
    mock_delay_ms: Optional[float] = None,
) -> RuntimeConfig:
    paths = RuntimePaths()
    paths.ensure_user_dirs()
    config_file = _resolve_config_path(config_path)
    raw = _load_yaml(config_file)

    model_cfg = raw.get("model", {})
    data_cfg = raw.get("data", {})
    th_cfg = raw.get("thresholds", {})
    dec_cfg = raw.get("decision", {})
    out_cfg = raw.get("output", {})
    sig_cfg = raw.get("signal", {})

    default_imgsz = model_cfg.get("imgsz", [736, 960])
    if imgsz is not None:
        default_imgsz = imgsz
    if len(default_imgsz) != 2:
        raise ValueError("imgsz must be [height, width], e.g. [736, 960]")

    save_vis_value = out_cfg.get("save_vis", True)
    if save_vis is not None:
        save_vis_value = save_vis
    if no_save_vis:
        save_vis_value = False

    return RuntimeConfig(
        model_path=_resolve_runtime_path(model or model_cfg.get("path", "models/yolo26s-seg.pt"), cli_override=model is not None),
        images_dir=_resolve_runtime_path(images or data_cfg.get("images", "data/images"), cli_override=images is not None),
        labels_dir=_resolve_runtime_path(labels or data_cfg.get("labels", "data/labels"), cli_override=labels is not None),
        output_base_dir=str(paths.resolve_cwd_path(output)) if output is not None else str(paths.default_output_dir),
        imgsz_h=int(default_imgsz[0]),
        imgsz_w=int(default_imgsz[1]),
        device=device or model_cfg.get("device", "auto"),
        half=bool(model_cfg.get("half", False)),
        retina_masks=bool(model_cfg.get("retina_masks", True)),
        low_conf=float(low_conf if low_conf is not None else th_cfg.get("low_conf", 0.25)),
        high_conf=float(high_conf if high_conf is not None else th_cfg.get("high_conf", 0.55)),
        iou=float(iou if iou is not None else th_cfg.get("iou", 0.50)),
        multi_gt_min_count=int(dec_cfg.get("multi_gt_min_count", 2)),
        save_vis=bool(save_vis_value),
        save_error_images=bool(out_cfg.get("save_error_images", True)),
        vis_all=bool(out_cfg.get("vis_all", True)),
        mock_delay_ms=float(mock_delay_ms if mock_delay_ms is not None else sig_cfg.get("mock_delay_ms", 0.0)),
        image_exts=data_cfg.get("image_exts", [".jpg", ".jpeg", ".png", ".bmp"]),
    )
