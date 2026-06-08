from __future__ import annotations

import numpy as np

from app.config import Config
from app.schemas import Detection
from app.vision.postprocess import Postprocessor
from app.vision.preprocess import PreprocessOutput


def _prep() -> PreprocessOutput:
    return PreprocessOutput(
        model_input_image=np.zeros((1024, 1024, 3), dtype=np.uint8),
        scale=1.0,
        pad_x=0,
        pad_y=0,
        roi_rect=[0, 0, 4024, 3036],
        original_shape=(3036, 4024),
        roi_shape=(3036, 4024),
        raw_image=np.zeros((3036, 4024, 3), dtype=np.uint8),
    )


def _tile_prep(roi_rect: list[int]) -> PreprocessOutput:
    width = roi_rect[2] - roi_rect[0]
    height = roi_rect[3] - roi_rect[1]
    return PreprocessOutput(
        model_input_image=np.zeros((1024, 1024, 3), dtype=np.uint8),
        scale=1024 / width,
        pad_x=0,
        pad_y=0,
        roi_rect=roi_rect,
        original_shape=(100, 200),
        roi_shape=(height, width),
        raw_image=np.zeros((100, 200, 3), dtype=np.uint8),
        scale_x=1024 / width,
        scale_y=1024 / height,
    )


def _det(
    score: float,
    box: list[float],
    class_name: str = "parcel",
    mask: np.ndarray | None = None,
) -> Detection:
    return Detection(
        class_id=0,
        class_name=class_name,
        score=score,
        box_model=box,
        mask_model=mask,
        mask_area_model=float(mask.sum()) if mask is not None else None,
    )


def test_low_confidence_filtered():
    cfg = Config()
    objects = Postprocessor(cfg).process([_det(0.1, [900, 100, 1100, 300])], _prep())
    assert objects == []


def test_belt_polygon_outside_filtered():
    cfg = Config()
    objects = Postprocessor(cfg).process([_det(0.9, [10, 100, 200, 300])], _prep())
    assert objects == []


def test_small_area_filtered():
    cfg = Config()
    objects = Postprocessor(cfg).process([_det(0.9, [900, 100, 905, 105])], _prep())
    assert objects == []


def test_duplicate_iou_dedup():
    cfg = Config()
    objects = Postprocessor(cfg).process(
        [_det(0.9, [900, 100, 1200, 500]), _det(0.8, [910, 110, 1210, 510])],
        _prep(),
    )
    assert len(objects) == 1
    assert objects[0].score == 0.9


def test_duplicate_mask_overlap_dedup_even_when_boxes_do_not_overlap():
    cfg = Config()
    mask = np.zeros((1024, 1024), dtype=np.uint8)
    mask[100:500, 900:1200] = 1
    objects = Postprocessor(cfg).process(
        [
            _det(0.9, [900, 100, 1200, 500], mask=mask),
            _det(0.8, [1300, 100, 1600, 500], mask=mask.copy()),
        ],
        _prep(),
    )
    assert len(objects) == 1
    assert objects[0].score == 0.9


def test_duplicate_mask_partial_overlap_dedup_by_smaller_mask_ratio():
    cfg = Config()
    mask_a = np.zeros((1024, 1024), dtype=np.uint8)
    mask_b = np.zeros((1024, 1024), dtype=np.uint8)
    mask_a[100:500, 700:1000] = 1
    mask_b[100:500, 950:1024] = 1
    objects = Postprocessor(cfg).process(
        [
            _det(0.9, [700, 100, 1000, 500], mask=mask_a),
            _det(0.8, [950, 100, 1250, 500], mask=mask_b),
        ],
        _prep(),
    )
    assert len(objects) == 1
    assert objects[0].score == 0.9


def test_tile_candidates_dedup_by_raw_mask_coordinates():
    cfg = Config()
    cfg.belt_polygon = [[0, 0], [200, 0], [200, 100], [0, 100]]
    cfg.postprocess.min_box_area_raw = 1
    cfg.postprocess.min_mask_area_raw = 1
    left_mask = np.zeros((1024, 1024), dtype=np.uint8)
    right_mask = np.zeros((1024, 1024), dtype=np.uint8)
    left_mask[:, 900:1024] = 1
    right_mask[:, 0:124] = 1
    postprocessor = Postprocessor(cfg)

    candidates = []
    candidates.extend(
        postprocessor.process_candidates(
            [_det(0.9, [0, 0, 1024, 1024], mask=left_mask)],
            _tile_prep([0, 0, 100, 100]),
            include_raw_mask=True,
        )
    )
    candidates.extend(
        postprocessor.process_candidates(
            [_det(0.8, [0, 0, 1024, 1024], mask=right_mask)],
            _tile_prep([90, 0, 190, 100]),
            include_raw_mask=True,
        )
    )
    objects = postprocessor.deduplicate_candidates(candidates)

    assert len(objects) == 1
    assert objects[0].score == 0.9


def test_mask_dedup_uses_transitive_connected_components():
    cfg = Config()
    cfg.belt_polygon = [[0, 0], [1300, 0], [1300, 600], [0, 600]]
    mask_a = np.zeros((1024, 1024), dtype=np.uint8)
    mask_b = np.zeros((1024, 1024), dtype=np.uint8)
    mask_c = np.zeros((1024, 1024), dtype=np.uint8)
    mask_a[100:500, 500:800] = 1
    mask_b[100:500, 750:950] = 1
    mask_c[100:500, 900:1024] = 1
    objects = Postprocessor(cfg).process(
        [
            _det(0.9, [500, 100, 800, 500], mask=mask_a),
            _det(0.8, [750, 100, 950, 500], mask=mask_b),
            _det(0.7, [900, 100, 1200, 500], mask=mask_c),
        ],
        _prep(),
    )

    assert len(objects) == 1
    assert objects[0].score == 0.9


def test_single_parcel_count():
    cfg = Config()
    objects = Postprocessor(cfg).process([_det(0.9, [900, 100, 1200, 500])], _prep())
    assert len(objects) == 1
