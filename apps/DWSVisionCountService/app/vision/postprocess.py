"""推理后处理：过滤、坐标还原、去重、计数。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.config import Config
from app.schemas import CountObject, Detection
from app.vision.geometry import (
    box_area,
    box_center,
    box_iou,
    clip_box_to_image,
    point_in_polygon,
    restore_box_to_original,
)
from app.vision.preprocess import PreprocessOutput


@dataclass
class _Candidate:
    obj: CountObject
    mask_model: np.ndarray | None = None
    mask_raw: np.ndarray | None = None


class Postprocessor:
    """把模型输出转换成可计数对象。"""

    def __init__(self, config: Config):
        self.config = config

    def process(self, detections: list[Detection], prep: PreprocessOutput) -> list[CountObject]:
        candidates = self.process_candidates(detections, prep)
        return self.deduplicate_candidates(candidates)

    def process_candidates(
        self,
        detections: list[Detection],
        prep: PreprocessOutput,
        include_raw_mask: bool = False,
    ) -> list[_Candidate]:
        candidates: list[_Candidate] = []
        image_height, image_width = prep.original_shape
        for det in detections:
            if det.class_name != self.config.model.target_class_name:
                continue
            if det.score < self.config.model.confidence_threshold:
                continue
            raw_box = self._restore_box(det.box_model, prep)
            raw_box = clip_box_to_image(raw_box, image_width, image_height)
            area = box_area(raw_box)
            if area < self.config.postprocess.min_box_area_raw:
                continue
            center = box_center(raw_box)
            if self.config.postprocess.require_center_in_belt_polygon:
                if not point_in_polygon(center, self.config.belt_polygon):
                    continue
            mask_area = self._mask_area_raw(det, prep)
            if mask_area is not None and mask_area < self.config.postprocess.min_mask_area_raw:
                continue
            candidates.append(
                _Candidate(
                    obj=CountObject(
                        class_id=det.class_id,
                        class_name=det.class_name,
                        score=det.score,
                        box=raw_box,
                        center=center,
                        box_area=area,
                        mask_area=mask_area,
                    ),
                    mask_model=det.mask_model,
                    mask_raw=(
                        self._mask_raw(det.mask_model, prep)
                        if include_raw_mask
                        else None
                    ),
                )
            )
        return candidates

    def deduplicate_objects(self, objects: list[CountObject]) -> list[CountObject]:
        """按框去重已还原到原图坐标的对象，供 tile 合并使用。"""
        candidates = [_Candidate(obj=obj) for obj in objects]
        return self.deduplicate_candidates(candidates)

    def deduplicate_candidates(self, candidates: list[_Candidate]) -> list[CountObject]:
        return [candidate.obj for candidate in self._deduplicate(candidates)]

    def _deduplicate(self, candidates: list[_Candidate]) -> list[_Candidate]:
        if not candidates:
            return []
        parents = list(range(len(candidates)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        for left in range(len(candidates)):
            for right in range(left + 1, len(candidates)):
                if self._is_duplicate(candidates[left], candidates[right]):
                    union(left, right)

        groups: dict[int, list[_Candidate]] = {}
        for index, candidate in enumerate(candidates):
            groups.setdefault(find(index), []).append(candidate)

        winners = [
            max(group, key=lambda item: item.obj.score)
            for group in groups.values()
        ]
        return sorted(winners, key=lambda item: item.obj.score, reverse=True)

    def _is_duplicate(self, candidate: _Candidate, existing: _Candidate) -> bool:
        if (
            box_iou(candidate.obj.box, existing.obj.box)
            >= self.config.postprocess.duplicate_iou_threshold
        ):
            return True
        candidate_mask = candidate.mask_raw if candidate.mask_raw is not None else candidate.mask_model
        existing_mask = existing.mask_raw if existing.mask_raw is not None else existing.mask_model
        mask_iou = self._mask_iou(candidate_mask, existing_mask)
        if mask_iou >= self.config.postprocess.duplicate_mask_iou_threshold:
            return True
        mask_overlap = self._mask_overlap(candidate_mask, existing_mask)
        return mask_overlap >= self.config.postprocess.duplicate_mask_overlap_threshold

    def _mask_iou(
        self,
        mask_a: np.ndarray | None,
        mask_b: np.ndarray | None,
    ) -> float:
        intersection, area_a, area_b = self._mask_intersection_and_areas(mask_a, mask_b)
        union = area_a + area_b - intersection
        if union <= 0:
            return 0.0
        return float(intersection / union)

    def _mask_overlap(
        self,
        mask_a: np.ndarray | None,
        mask_b: np.ndarray | None,
    ) -> float:
        intersection, area_a, area_b = self._mask_intersection_and_areas(mask_a, mask_b)
        smaller = min(area_a, area_b)
        if smaller <= 0:
            return 0.0
        return float(intersection / smaller)

    def _mask_intersection_and_areas(
        self,
        mask_a: np.ndarray | None,
        mask_b: np.ndarray | None,
    ) -> tuple[int, int, int]:
        if mask_a is None or mask_b is None or mask_a.shape != mask_b.shape:
            return 0, 0, 0
        a = mask_a > 0
        b = mask_b > 0
        intersection = int(np.logical_and(a, b).sum())
        return intersection, int(a.sum()), int(b.sum())

    def _mask_area_raw(self, det: Detection, prep: PreprocessOutput) -> float | None:
        if det.mask_area_model is None:
            return None
        scale_x = prep.scale_x or prep.scale
        scale_y = prep.scale_y or prep.scale
        return float(det.mask_area_model) / (scale_x * scale_y)

    def _mask_raw(self, mask_model: np.ndarray | None, prep: PreprocessOutput) -> np.ndarray | None:
        if mask_model is None:
            return None
        image_height, image_width = prep.original_shape
        roi_x1, roi_y1, roi_x2, roi_y2 = prep.roi_rect
        roi_width = roi_x2 - roi_x1
        roi_height = roi_y2 - roi_y1
        scale_x = prep.scale_x or prep.scale
        scale_y = prep.scale_y or prep.scale
        resized_width = max(1, min(mask_model.shape[1] - prep.pad_x, int(round(roi_width * scale_x))))
        resized_height = max(1, min(mask_model.shape[0] - prep.pad_y, int(round(roi_height * scale_y))))
        crop = mask_model[
            prep.pad_y : prep.pad_y + resized_height,
            prep.pad_x : prep.pad_x + resized_width,
        ]
        raw_crop = cv2.resize(
            (crop > 0).astype(np.uint8),
            (roi_width, roi_height),
            interpolation=cv2.INTER_NEAREST,
        )
        raw_mask = np.zeros((image_height, image_width), dtype=np.uint8)
        raw_mask[roi_y1:roi_y2, roi_x1:roi_x2] = raw_crop
        return raw_mask

    def _restore_box(self, box: list[float], prep: PreprocessOutput) -> list[float]:
        scale_x = prep.scale_x or prep.scale
        scale_y = prep.scale_y or prep.scale
        if abs(scale_x - scale_y) < 1e-9:
            return restore_box_to_original(box, prep.roi_rect, scale_x, prep.pad_x, prep.pad_y)
        roi_x1, roi_y1, _, _ = prep.roi_rect
        x1, y1, x2, y2 = box
        return [
            (x1 - prep.pad_x) / scale_x + roi_x1,
            (y1 - prep.pad_y) / scale_y + roi_y1,
            (x2 - prep.pad_x) / scale_x + roi_x1,
            (y2 - prep.pad_y) / scale_y + roi_y1,
        ]
