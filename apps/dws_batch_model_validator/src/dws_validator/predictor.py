# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np


@dataclass
class Detection:
    xyxy: Tuple[float, float, float, float]
    conf: float
    cls: int
    mask: Optional[np.ndarray] = None


def _openvino_xml_files(model_dir: Path) -> list[Path]:
    return sorted(p for p in model_dir.glob("*.xml") if p.is_file())


def detect_model_format(model_path: str | Path) -> str:
    path = Path(model_path)
    if path.is_file() and path.suffix.lower() == ".pt":
        return "pt"
    if path.is_file() and path.suffix.lower() == ".xml":
        return "openvino"
    if path.is_dir() and path.name.lower().endswith("_openvino_model") and _openvino_xml_files(path):
        return "openvino"
    return "unknown"


def resolve_model_path_for_ultralytics(model_path: str | Path) -> Path:
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError("找不到模型文件，请重新选择 .pt 文件或 OpenVINO 模型目录/.xml 文件。")

    model_format = detect_model_format(path)
    if model_format == "pt":
        return path
    if model_format == "openvino":
        model_dir = path.parent if path.is_file() else path
        xml_files = _openvino_xml_files(model_dir)
        if len(xml_files) != 1:
            raise FileNotFoundError("OpenVINO 模型目录必须包含且只包含一个 .xml 文件。")
        bin_file = xml_files[0].with_suffix(".bin")
        if not bin_file.exists():
            raise FileNotFoundError(f"OpenVINO 模型缺少对应的 .bin 权重文件：{bin_file}")
        if not model_dir.name.lower().endswith("_openvino_model"):
            raise FileNotFoundError("OpenVINO 模型目录名必须以 _openvino_model 结尾，请选择 Ultralytics 导出的 OpenVINO 目录或其中的 .xml 文件。")
        return model_dir

    raise FileNotFoundError("模型格式不支持，请选择 .pt 文件或 Ultralytics 导出的 OpenVINO 模型目录/.xml 文件。")


class YoloSegPredictor:
    def __init__(
        self,
        model_path: str,
        imgsz_h: int,
        imgsz_w: int,
        device: str = "auto",
        half: bool = False,
        retina_masks: bool = True,
    ) -> None:
        self.model_path = str(model_path)
        self.ultralytics_model_path = resolve_model_path_for_ultralytics(self.model_path)
        self.model_format = detect_model_format(self.ultralytics_model_path)
        self.device = "cpu" if self.model_format == "openvino" else self._resolve_device(device)
        self.actual_device_label = "OpenVINO CPU" if self.model_format == "openvino" else ("CUDA GPU" if self.device not in {"cpu", "CPU"} else "CPU")
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("当前环境未安装 ultralytics，无法执行 YOLO segmentation 推理。") from exc
        except Exception as exc:
            raise RuntimeError(f"ultralytics 导入失败：{exc}") from exc
        self.imgsz = (imgsz_h, imgsz_w)
        self.half = bool(half)
        self.retina_masks = bool(retina_masks)
        self.model = YOLO(str(self.ultralytics_model_path))

        dummy = np.zeros((imgsz_h, imgsz_w, 3), dtype=np.uint8)
        try:
            _ = self.model.predict(
                source=dummy,
                imgsz=self.imgsz,
                conf=0.01,
                iou=0.50,
                device=self.device,
                half=self.half,
                retina_masks=self.retina_masks,
                verbose=False,
            )
        except Exception as exc:
            if self.model_format == "openvino":
                raise RuntimeError(f"OpenVINO 模型加载或预热失败：{exc}") from exc

    @staticmethod
    def _resolve_device(device: str) -> str:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("当前环境未安装 torch，无法执行模型推理。") from exc
        except Exception as exc:
            raise RuntimeError(f"torch 导入失败：{exc}") from exc

        normalized = "auto" if device is None else str(device).strip().lower()
        if normalized in {"自动", "auto"}:
            return "0" if torch.cuda.is_available() else "cpu"
        if normalized in {"cpu"}:
            return "cpu"
        if normalized in {"gpu", "cuda", "cuda:0", "0"}:
            if not torch.cuda.is_available():
                raise RuntimeError("当前电脑未检测到可用 NVIDIA CUDA 推理环境，请改用 CPU 或安装匹配的 NVIDIA 驱动和 PyTorch CUDA 运行环境。")
            return "0"
        if normalized.startswith("cuda"):
            if not torch.cuda.is_available():
                raise RuntimeError("当前电脑未检测到可用 NVIDIA CUDA 推理环境，请改用 CPU 或安装匹配的 NVIDIA 驱动和 PyTorch CUDA 运行环境。")
            return normalized
        if normalized.isdigit():
            if not torch.cuda.is_available():
                raise RuntimeError("当前电脑未检测到可用 NVIDIA CUDA 推理环境，请改用 CPU 或安装匹配的 NVIDIA 驱动和 PyTorch CUDA 运行环境。")
            return normalized
        return str(device)

    def predict(self, image_bgr: np.ndarray, low_conf: float, iou: float) -> Tuple[List[Detection], object]:
        results = self.model.predict(
            source=image_bgr,
            imgsz=self.imgsz,
            conf=low_conf,
            iou=iou,
            device=self.device,
            half=self.half,
            retina_masks=self.retina_masks,
            verbose=False,
        )
        r = results[0]
        detections: List[Detection] = []

        if r.boxes is None or len(r.boxes) == 0:
            return detections, r

        boxes_xyxy = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        clss = r.boxes.cls.cpu().numpy().astype(int)

        masks = None
        if getattr(r, "masks", None) is not None and r.masks is not None and r.masks.data is not None:
            try:
                masks = r.masks.data.cpu().numpy()
            except Exception:
                masks = None

        for i in range(len(confs)):
            mask_i = masks[i] if masks is not None and i < len(masks) else None
            detections.append(
                Detection(
                    xyxy=tuple(float(x) for x in boxes_xyxy[i]),
                    conf=float(confs[i]),
                    cls=int(clss[i]),
                    mask=mask_i,
                )
            )
        detections.sort(key=lambda d: d.conf, reverse=True)
        return detections, r
