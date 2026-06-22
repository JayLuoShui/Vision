"""Native OpenVINO 推理后端。"""

from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np
from loguru import logger

from app.config import Config
from app.schemas import Detection
from app.utils.errors import InferenceError, ModelNotLoadedError
from app.vision.backends.base import BaseVisionBackend


class NativeOpenVINOBackend(BaseVisionBackend):
    """直接使用 OpenVINO Runtime，避开 Ultralytics Python 推理封装。"""

    def __init__(self, config: Config):
        self.config = config
        self.model_path = Path(config.get_model_path())
        self.core = None
        self.compiled_model = None
        self.infer_request = None
        self.outputs = []
        self._infer_lock = threading.Lock()

    def load(self) -> None:
        try:
            from openvino import Core

            xml_path = self._resolve_xml_path()
            if not xml_path.exists():
                logger.warning("model xml not found: {}", xml_path)
                return
            self.core = Core()
            model = self.core.read_model(str(xml_path))
            properties = {"PERFORMANCE_HINT": self.config.model.performance_hint}
            self.compiled_model = self.core.compile_model(
                model,
                self.config.model.device,
                properties,
            )
            self.infer_request = self.compiled_model.create_infer_request()
            self.outputs = [self.compiled_model.output(i) for i in range(len(self.compiled_model.outputs))]
            logger.info("loaded Native OpenVINO model: {}", xml_path)
        except Exception as exc:
            self.compiled_model = None
            self.infer_request = None
            self.outputs = []
            logger.exception("failed to load native openvino model: {}", exc)

    def is_loaded(self) -> bool:
        return self.compiled_model is not None

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
            tensor = self._to_input_tensor(image_bgr)
            with self._infer_lock:
                self.infer_request.infer([tensor])
                outputs = [
                    self.infer_request.get_output_tensor(index).data
                    for index in range(len(self.outputs))
                ]
                return self._convert_outputs(outputs, image_bgr.shape[:2])
        except Exception as exc:
            raise InferenceError(f"native openvino inference failed: {exc}") from exc

    def _resolve_xml_path(self) -> Path:
        if self.model_path.is_dir():
            xml_files = sorted(self.model_path.glob("*.xml"))
            if not xml_files:
                return self.model_path / "model.xml"
            return xml_files[0]
        return self.model_path

    def _to_input_tensor(self, image_bgr: np.ndarray) -> np.ndarray:
        image_rgb = image_bgr[..., ::-1].astype(np.float32) / 255.0
        tensor = np.transpose(image_rgb, (2, 0, 1))[None]
        return np.ascontiguousarray(tensor, dtype=np.float32)

    def _convert_outputs(
        self,
        outputs: list[np.ndarray],
        image_shape: tuple[int, int],
    ) -> list[Detection]:
        predictions, prototypes = self._split_outputs(outputs)
        rows = predictions[0]
        scores = rows[:, 4]
        keep_indexes = np.where(scores >= self.config.model.confidence_threshold)[0]
        if keep_indexes.size == 0:
            return []

        kept_rows = rows[keep_indexes]
        boxes = kept_rows[:, :4].astype(np.float32)
        scores = kept_rows[:, 4].astype(np.float32)
        class_ids = np.rint(kept_rows[:, 5]).astype(np.int32)
        mask_coeffs = kept_rows[:, 6:].astype(np.float32)
        masks = self._process_masks(prototypes[0], mask_coeffs, boxes, image_shape)
        class_names = {int(k): v for k, v in self.config.model.class_names.items()}

        detections: list[Detection] = []
        for index, box in enumerate(boxes):
            class_id = int(class_ids[index])
            mask_model = masks[index] if masks is not None else None
            detections.append(
                Detection(
                    class_id=class_id,
                    class_name=class_names.get(class_id, str(class_id)),
                    score=float(scores[index]),
                    box_model=[float(v) for v in box.tolist()],
                    mask_model=mask_model,
                    mask_area_model=float(mask_model.sum()) if mask_model is not None else None,
                )
            )
        return detections

    def _split_outputs(self, outputs: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        predictions = None
        prototypes = None
        for output in outputs:
            array = np.asarray(output)
            if array.ndim == 3 and array.shape[-1] >= 6:
                predictions = array
            elif array.ndim == 4 and array.shape[1] == 32:
                prototypes = array
        if predictions is None or prototypes is None:
            raise ValueError("unexpected native openvino output shapes")
        return predictions, prototypes

    def _process_masks(
        self,
        prototypes: np.ndarray,
        coeffs: np.ndarray,
        boxes: np.ndarray,
        image_shape: tuple[int, int],
    ) -> np.ndarray | None:
        if coeffs.size == 0:
            return None
        channels, mask_height, mask_width = prototypes.shape
        masks = coeffs @ prototypes.reshape(channels, -1)
        masks = masks.reshape(-1, mask_height, mask_width)

        image_height, image_width = image_shape
        ratio = np.array(
            [
                mask_width / image_width,
                mask_height / image_height,
                mask_width / image_width,
                mask_height / image_height,
            ],
            dtype=np.float32,
        )
        masks = self._crop_masks(masks, boxes * ratio)
        if (mask_height, mask_width) == (image_height, image_width):
            return (masks > 0.0).astype(np.uint8)
        resized = [
            cv2.resize(mask, (image_width, image_height), interpolation=cv2.INTER_LINEAR)
            for mask in masks
        ]
        return (np.stack(resized, axis=0) > 0.0).astype(np.uint8)

    def _crop_masks(self, masks: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        cropped = masks.copy()
        _, height, width = cropped.shape
        for index, box in enumerate(boxes):
            x1, y1, x2, y2 = np.maximum(box, 0).round().astype(np.int32)
            x1 = max(0, min(width, int(x1)))
            x2 = max(0, min(width, int(x2)))
            y1 = max(0, min(height, int(y1)))
            y2 = max(0, min(height, int(y2)))
            cropped[index, :y1] = 0
            cropped[index, y2:] = 0
            cropped[index, :, :x1] = 0
            cropped[index, :, x2:] = 0
        return cropped
