"""Ultralytics OpenVINO 推理后端。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from loguru import logger

from app.config import Config
from app.schemas import Detection
from app.utils.errors import InferenceError, ModelNotLoadedError
from app.vision.backends.base import BaseVisionBackend


class UltralyticsOpenVINOBackend(BaseVisionBackend):
    """第一版生产后端：用 Ultralytics 加载 OpenVINO 导出目录。"""

    def __init__(self, config: Config):
        self.config = config
        self.model = None
        self.model_path = Path(config.model.model_path)

    def load(self) -> None:
        try:
            from ultralytics import YOLO

            if not self.model_path.exists():
                logger.warning("model path not found: {}", self.model_path)
                return
            self.model = YOLO(str(self.model_path), task=self._model_task())
            logger.info("loaded Ultralytics OpenVINO model: {}", self.model_path)
        except Exception as exc:
            self.model = None
            logger.exception("failed to load model: {}", exc)

    def is_loaded(self) -> bool:
        return self.model is not None

    def warmup(self) -> None:
        if self.is_loaded():
            dummy = np.zeros(
                (self.config.model.imgsz, self.config.model.imgsz, 3),
                dtype=np.uint8,
            )
            self.predict(dummy)

    def predict(self, image_bgr: np.ndarray) -> list[Detection]:
        if not self.is_loaded():
            raise ModelNotLoadedError()
        try:
            results = self.model.predict(
                source=image_bgr,
                imgsz=self.config.model.imgsz,
                conf=self.config.model.confidence_threshold,
                iou=self.config.model.iou_threshold,
                device=self.config.model.device,
                verbose=False,
                batch=1,
            )
            return self._convert_results(results)
        except Exception as exc:
            raise InferenceError(f"inference failed: {exc}") from exc

    def _convert_results(self, results) -> list[Detection]:
        detections: list[Detection] = []
        if not results:
            return detections
        class_names = {int(k): v for k, v in self.config.model.class_names.items()}
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None or getattr(boxes, "xyxy", None) is None:
                continue
            xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else np.asarray(boxes.xyxy)
            conf = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else np.asarray(boxes.conf)
            cls = boxes.cls.cpu().numpy() if hasattr(boxes.cls, "cpu") else np.asarray(boxes.cls)
            masks_data = None
            masks = getattr(result, "masks", None)
            if masks is not None and getattr(masks, "data", None) is not None:
                masks_data = masks.data.cpu().numpy() if hasattr(masks.data, "cpu") else np.asarray(masks.data)
            for index, box in enumerate(xyxy):
                class_id = int(cls[index])
                mask_model = masks_data[index] if masks_data is not None and index < len(masks_data) else None
                detections.append(
                    Detection(
                        class_id=class_id,
                        class_name=class_names.get(class_id, str(class_id)),
                        score=float(conf[index]),
                        box_model=[float(v) for v in box.tolist()],
                        mask_model=mask_model,
                        mask_area_model=float(mask_model.sum()) if mask_model is not None else None,
                    )
                )
        return detections

    def _model_task(self) -> str:
        metadata_path = self.model_path / "metadata.yaml" if self.model_path.is_dir() else self.model_path.parent / "metadata.yaml"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as file:
                metadata = yaml.safe_load(file) or {}
            task = metadata.get("task")
            if task:
                return str(task)
        return "segment"
