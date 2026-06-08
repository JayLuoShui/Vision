"""包裹计数主入口。"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from statistics import mean

import numpy as np
import yaml
from loguru import logger

from app.config import Config
from app.schemas import CountResult, DecodedImage, ImageMeta
from app.utils.errors import (
    ImageTooLargeError,
    InferenceError,
    ModelNotLoadedError,
    VisionServiceError,
)
from app.utils.async_saver import save_image_async, save_json_async
from app.utils.debug_draw import draw_debug_image
from app.utils.image_io import decode_image_bytes_with_info
from app.vision.backends.native_openvino_backend import NativeOpenVINOBackend
from app.vision.backends.ultralytics_openvino_backend import UltralyticsOpenVINOBackend
from app.vision.postprocess import Postprocessor
from app.vision.preprocess import Preprocessor
from app.vision.tiling import make_2x2_tile_windows


class ParcelCounter:
    """完整链路：bytes 解码 -> 预处理 -> 推理 -> 后处理 -> 数量。"""

    def __init__(self, config: Config):
        self.config = config
        self.preprocessor = Preprocessor(config)
        self.postprocessor = Postprocessor(config)
        self.backend = self._create_backend()
        self.last_task_time: str | None = None
        self.processing_times: list[int] = []

    def _create_backend(self):
        if self.config.model.backend == "native_openvino":
            return NativeOpenVINOBackend(self.config)
        return UltralyticsOpenVINOBackend(self.config)

    def load(self) -> None:
        self.backend.load()
        if self.backend.is_loaded():
            self.backend.warmup()

    def count_bytes(self, meta: ImageMeta, image_bytes: bytes) -> CountResult:
        total_start = time.perf_counter()
        if meta.image_len > self.config.service.max_image_bytes:
            return self._error_result(meta.task_id, ImageTooLargeError(), 0, 0)
        try:
            decode_start = time.perf_counter()
            decoded = decode_image_bytes_with_info(
                meta,
                image_bytes,
                reduce_factor=self.config.service.decode_reduce_factor,
            )
            decode_ms = int((time.perf_counter() - decode_start) * 1000)
            result = self._count_decoded(decoded)
            result.decode_time_ms = decode_ms
            result.processing_time_ms = int((time.perf_counter() - total_start) * 1000)
            return result
        except VisionServiceError as exc:
            return self._error_result(meta.task_id, exc, meta.width or 0, meta.height or 0, total_start=total_start)
        except Exception as exc:
            logger.exception("count_bytes unknown error: {}", exc)
            return self._error_result(
                meta.task_id,
                VisionServiceError(5000, str(exc)),
                meta.width or 0,
                meta.height or 0,
                total_start=total_start,
            )

    def count_image(
        self,
        image_bgr: np.ndarray,
        task_id: str | None = None,
        source_encoding: str = "array",
    ) -> CountResult:
        task_id = task_id or datetime.now().strftime("%Y%m%d%H%M%S%f")
        total_start = time.perf_counter()
        prep_ms = infer_ms = post_ms = 0
        height, width = image_bgr.shape[:2] if image_bgr is not None else (0, 0)
        try:
            if not self.backend.is_loaded():
                raise ModelNotLoadedError()
            decoded = DecodedImage(
                task_id=task_id,
                image_bgr=image_bgr,
                width=width,
                height=height,
                source_encoding=source_encoding,
            )
            return self._count_decoded(decoded, total_start=total_start)
        except VisionServiceError as exc:
            if self.config.debug.save_failed_image and image_bgr is not None:
                self._save_failed_image(image_bgr, task_id, exc)
            return self._error_result(task_id, exc, width, height, prep_ms, infer_ms, post_ms, total_start)
        except Exception as exc:
            logger.exception("count_image unknown error: {}", exc)
            error = InferenceError(str(exc))
            if self.config.debug.save_failed_image and image_bgr is not None:
                self._save_failed_image(image_bgr, task_id, error)
            return self._error_result(task_id, error, width, height, prep_ms, infer_ms, post_ms, total_start)

    def _count_decoded(
        self,
        decoded: DecodedImage,
        total_start: float | None = None,
    ) -> CountResult:
        if self.config.preprocess.mode == "roi_polygon_letterbox_tile_2x2":
            return self._count_decoded_tiled(decoded, total_start)
        total_start = total_start or time.perf_counter()
        start = time.perf_counter()
        prep = self.preprocessor.process(decoded)
        prep_ms = int((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        detections = self.backend.predict(prep.model_input_image)
        infer_ms = int((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        objects = self.postprocessor.process(detections, prep)
        post_ms = int((time.perf_counter() - start) * 1000)
        processing_ms = int((time.perf_counter() - total_start) * 1000)
        confidence = mean([obj.score for obj in objects]) if objects else 1.0
        message = "ok" if objects else "ok_empty"
        self._record_time(processing_ms)
        if self.config.debug.save_debug_image:
            self._save_debug_image(
                decoded.image_bgr,
                objects,
                decoded.task_id,
                len(objects),
                processing_ms,
                decoded.original_width or decoded.width,
                decoded.original_height or decoded.height,
            )
        return CountResult(
            task_id=decoded.task_id,
            code=0,
            message=message,
            parcel_count=len(objects),
            confidence=float(confidence),
            processing_time_ms=processing_ms,
            decode_time_ms=0,
            preprocess_time_ms=prep_ms,
            inference_time_ms=infer_ms,
            postprocess_time_ms=post_ms,
            model="yolo26n-seg-openvino",
            image_width=decoded.original_width or decoded.width,
            image_height=decoded.original_height or decoded.height,
            objects=objects,
        )

    def _count_decoded_tiled(
        self,
        decoded: DecodedImage,
        total_start: float | None = None,
    ) -> CountResult:
        total_start = total_start or time.perf_counter()
        original_width = decoded.original_width or decoded.width
        original_height = decoded.original_height or decoded.height
        roi_x1, roi_y1, roi_x2, roi_y2 = self.preprocessor._clipped_roi(
            original_width,
            original_height,
        )
        windows = make_2x2_tile_windows(
            roi_x2 - roi_x1,
            roi_y2 - roi_y1,
            self.config.preprocess.tile_overlap_ratio,
        )
        prep_ms = infer_ms = post_ms = 0
        candidates = []
        for window in windows:
            tile_rect = (
                roi_x1 + window.x1,
                roi_y1 + window.y1,
                roi_x1 + window.x2,
                roi_y1 + window.y2,
            )
            start = time.perf_counter()
            prep = self.preprocessor.process(decoded, roi_override=tile_rect)
            prep_ms += int((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            detections = self.backend.predict(prep.model_input_image)
            infer_ms += int((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            candidates.extend(
                self.postprocessor.process_candidates(
                    detections,
                    prep,
                    include_raw_mask=True,
                )
            )
            post_ms += int((time.perf_counter() - start) * 1000)

        objects = self.postprocessor.deduplicate_candidates(candidates)
        processing_ms = int((time.perf_counter() - total_start) * 1000)
        confidence = mean([obj.score for obj in objects]) if objects else 1.0
        message = "ok" if objects else "ok_empty"
        self._record_time(processing_ms)
        if self.config.debug.save_debug_image:
            self._save_debug_image(
                decoded.image_bgr,
                objects,
                decoded.task_id,
                len(objects),
                processing_ms,
                original_width,
                original_height,
            )
        return CountResult(
            task_id=decoded.task_id,
            code=0,
            message=message,
            parcel_count=len(objects),
            confidence=float(confidence),
            processing_time_ms=processing_ms,
            decode_time_ms=0,
            preprocess_time_ms=prep_ms,
            inference_time_ms=infer_ms,
            postprocess_time_ms=post_ms,
            model="yolo26n-seg-openvino",
            image_width=original_width,
            image_height=original_height,
            objects=objects,
        )

    def health(self) -> dict:
        avg = int(mean(self.processing_times)) if self.processing_times else 0
        metadata = self._model_metadata()
        args = metadata.get("args", {}) if isinstance(metadata.get("args", {}), dict) else {}
        return {
            "status": "running",
            "model_loaded": self.backend.is_loaded(),
            "device": self.config.model.device,
            "backend": self.config.model.backend,
            "model_path": self.config.model.model_path,
            "model_task": metadata.get("task", ""),
            "model_int8": bool(args.get("int8", False)),
            "version": self.config.service.version,
            "last_task_time": self.last_task_time,
            "avg_processing_time_ms": avg,
        }

    def _model_metadata(self) -> dict:
        model_path = Path(self.config.model.model_path)
        metadata_path = model_path / "metadata.yaml" if model_path.is_dir() else model_path.parent / "metadata.yaml"
        if not metadata_path.exists():
            return {}
        with open(metadata_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}

    def _record_time(self, processing_ms: int) -> None:
        self.last_task_time = datetime.now().isoformat(timespec="seconds")
        self.processing_times.append(processing_ms)
        self.processing_times = self.processing_times[-100:]

    def _save_debug_image(
        self,
        image_bgr: np.ndarray,
        objects,
        task_id: str,
        parcel_count: int,
        processing_ms: int,
        original_width: int,
        original_height: int,
    ) -> None:
        safe_task_id = "".join(ch for ch in task_id if ch.isalnum() or ch in ("-", "_")) or "task"
        filename = f"{datetime.now():%Y%m%d_%H%M%S_%f}_{safe_task_id}_count{parcel_count}.jpg"
        path = Path(self.config.debug.debug_dir) / filename
        image = draw_debug_image(
            image_bgr,
            objects,
            self.config.belt_polygon,
            parcel_count,
            processing_ms,
            original_width=original_width,
            original_height=original_height,
        )
        save_image_async(path, image)

    def _save_failed_image(self, image_bgr: np.ndarray, task_id: str, exc: VisionServiceError) -> None:
        safe_task_id = "".join(ch for ch in task_id if ch.isalnum() or ch in ("-", "_")) or "task"
        stem = f"{datetime.now():%Y%m%d_%H%M%S_%f}_{safe_task_id}_code{exc.code}"
        image_path = Path(self.config.debug.failed_dir) / f"{stem}.jpg"
        json_path = Path(self.config.debug.failed_dir) / f"{stem}.json"
        save_image_async(image_path, image_bgr)
        save_json_async(json_path, {"task_id": task_id, "code": exc.code, "message": exc.message})

    def _error_result(
        self,
        task_id: str,
        exc: VisionServiceError,
        width: int,
        height: int,
        prep_ms: int = 0,
        infer_ms: int = 0,
        post_ms: int = 0,
        total_start: float | None = None,
    ) -> CountResult:
        processing_ms = int((time.perf_counter() - total_start) * 1000) if total_start else 0
        return CountResult(
            task_id=task_id,
            code=exc.code,
            message=exc.message,
            parcel_count=0,
            confidence=0.0,
            processing_time_ms=processing_ms,
            decode_time_ms=0,
            preprocess_time_ms=prep_ms,
            inference_time_ms=infer_ms,
            postprocess_time_ms=post_ms,
            model="yolo26n-seg-openvino",
            image_width=width,
            image_height=height,
            objects=[],
        )
