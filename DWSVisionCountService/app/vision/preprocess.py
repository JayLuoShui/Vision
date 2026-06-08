"""图像预处理：忽略区、多边形 mask、ROI 裁剪、letterbox。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from loguru import logger

from app.config import Config
from app.schemas import DecodedImage


@dataclass
class PreprocessOutput:
    model_input_image: np.ndarray
    scale: float
    pad_x: int
    pad_y: int
    roi_rect: list[int]
    original_shape: tuple[int, int]
    roi_shape: tuple[int, int]
    raw_image: np.ndarray
    scale_x: float | None = None
    scale_y: float | None = None

    @property
    def input_tensor(self) -> np.ndarray:
        """兼容旧 runner：返回 NCHW float tensor。"""
        image = self.model_input_image.astype(np.float32) / 255.0
        return np.expand_dims(np.transpose(image, (2, 0, 1)), axis=0)


def letterbox(image: np.ndarray, target_size: int = 1024, color: tuple[int, int, int] = (0, 0, 0)):
    """保持比例缩放并居中填充到固定方形尺寸。"""
    if image is None or image.size == 0:
        raise ValueError("image is empty")
    height, width = image.shape[:2]
    scale = min(target_size / width, target_size / height)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    pad_x = (target_size - new_width) // 2
    pad_y = (target_size - new_height) // 2
    output = cv2.copyMakeBorder(
        resized,
        pad_y,
        target_size - new_height - pad_y,
        pad_x,
        target_size - new_width - pad_x,
        cv2.BORDER_CONSTANT,
        value=color,
    )
    return output, scale, pad_x, pad_y


class Preprocessor:
    """现场图片预处理流水线。"""

    def __init__(self, config: Config):
        self.config = config
        self._combined_mask_cache: dict[tuple, np.ndarray] = {}

    def process(
        self,
        decoded: DecodedImage,
        roi_override: tuple[int, int, int, int] | None = None,
    ) -> PreprocessOutput:
        image = decoded.image_bgr
        if image is None or image.size == 0:
            raise ValueError("image is empty")
        decoded_height, decoded_width = image.shape[:2]
        original_width = decoded.original_width or decoded.width
        original_height = decoded.original_height or decoded.height
        decode_scale_x = decoded.decode_scale_x or decoded_width / original_width
        decode_scale_y = decoded.decode_scale_y or decoded_height / original_height
        if (original_width, original_height) != (self.config.camera.raw_width, self.config.camera.raw_height):
            logger.warning("unexpected image size: {}x{}", original_width, original_height)

        if roi_override is None:
            x1, y1, x2, y2 = self._clipped_roi(original_width, original_height)
        else:
            x1, y1, x2, y2 = self._clipped_rect(
                roi_override,
                original_width,
                original_height,
            )
        dx1 = int(round(x1 * decode_scale_x))
        dy1 = int(round(y1 * decode_scale_y))
        dx2 = int(round(x2 * decode_scale_x))
        dy2 = int(round(y2 * decode_scale_y))
        dx1, dy1, dx2, dy2 = self._clipped_decode_roi(dx1, dy1, dx2, dy2, decoded_width, decoded_height)
        roi_image = image[dy1:dy2, dx1:dx2]
        combined_mask = self._get_combined_mask(
            roi_image.shape[:2],
            x1,
            y1,
            decode_scale_x,
            decode_scale_y,
        )
        work = (
            cv2.copyTo(roi_image, combined_mask)
            if combined_mask is not None
            else roi_image.copy()
        )

        model_image, scale, pad_x, pad_y = letterbox(
            work,
            target_size=self.config.preprocess.infer_imgsz,
            color=(0, 0, 0),
        )
        return PreprocessOutput(
            model_input_image=model_image,
            scale=scale * decode_scale_x,
            pad_x=pad_x,
            pad_y=pad_y,
            roi_rect=[x1, y1, x2, y2],
            original_shape=(original_height, original_width),
            roi_shape=work.shape[:2],
            raw_image=image,
            scale_x=scale * decode_scale_x,
            scale_y=scale * decode_scale_y,
        )

    def _get_combined_mask(
        self,
        roi_shape: tuple[int, int],
        roi_x1: int,
        roi_y1: int,
        decode_scale_x: float,
        decode_scale_y: float,
    ) -> np.ndarray | None:
        mask_polygon = self.config.preprocess.mask_outside_polygon
        mask_ignore = self.config.preprocess.mask_ignore_regions
        if not mask_polygon and not mask_ignore:
            return None

        key = (
            roi_shape,
            roi_x1,
            roi_y1,
            decode_scale_x,
            decode_scale_y,
            mask_polygon,
            mask_ignore,
            tuple(tuple(point) for point in self.config.belt_polygon),
            tuple(
                (region.x1, region.y1, region.x2, region.y2)
                for region in self.config.ignore_regions
            ),
        )
        cached = self._combined_mask_cache.get(key)
        if cached is not None:
            return cached

        height, width = roi_shape
        mask = np.zeros(roi_shape, dtype=np.uint8) if mask_polygon else np.full(roi_shape, 255, dtype=np.uint8)
        if mask_polygon:
            polygon = np.array(
                [
                    [
                        int(round((x - roi_x1) * decode_scale_x)),
                        int(round((y - roi_y1) * decode_scale_y)),
                    ]
                    for x, y in self.config.belt_polygon
                ],
                dtype=np.int32,
            ).reshape((-1, 1, 2))
            cv2.fillPoly(mask, [polygon], 255)

        if mask_ignore:
            for region in self.config.ignore_regions:
                x1 = max(0, min(width, int(round((region.x1 - roi_x1) * decode_scale_x))))
                y1 = max(0, min(height, int(round((region.y1 - roi_y1) * decode_scale_y))))
                x2 = max(0, min(width, int(round((region.x2 - roi_x1) * decode_scale_x))))
                y2 = max(0, min(height, int(round((region.y2 - roi_y1) * decode_scale_y))))
                if x2 > x1 and y2 > y1:
                    mask[y1:y2, x1:x2] = 0

        self._combined_mask_cache[key] = mask
        return mask

    def _clipped_roi(self, width: int, height: int) -> tuple[int, int, int, int]:
        rect = self.config.detect_roi_rect
        return self._clipped_rect((rect.x1, rect.y1, rect.x2, rect.y2), width, height)

    def _clipped_rect(
        self,
        rect: tuple[int, int, int, int],
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = rect
        x1 = max(0, min(width - 1, x1))
        y1 = max(0, min(height - 1, y1))
        x2 = max(x1 + 1, min(width, x2))
        y2 = max(y1 + 1, min(height, y2))
        return x1, y1, x2, y2

    def _clipped_decode_roi(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:
        x1 = max(0, min(width - 1, x1))
        y1 = max(0, min(height - 1, y1))
        x2 = max(x1 + 1, min(width, x2))
        y2 = max(y1 + 1, min(height, y2))
        return x1, y1, x2, y2
