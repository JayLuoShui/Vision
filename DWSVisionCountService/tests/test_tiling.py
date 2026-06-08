from __future__ import annotations

import numpy as np

from app.config import Config, DetectROIRect
from app.schemas import Detection
from app.vision.counter import ParcelCounter
from app.vision.tiling import make_2x2_tile_windows


def test_make_2x2_tile_windows_cover_full_roi_with_overlap():
    windows = make_2x2_tile_windows(200, 100, overlap_ratio=0.1)

    assert [(w.x1, w.y1, w.x2, w.y2) for w in windows] == [
        (0, 0, 110, 55),
        (90, 0, 200, 55),
        (0, 45, 110, 100),
        (90, 45, 200, 100),
    ]


def test_tile_2x2_mode_runs_four_tile_inferences():
    cfg = Config()
    cfg.camera.raw_width = 200
    cfg.camera.raw_height = 200
    cfg.preprocess.mode = "roi_polygon_letterbox_tile_2x2"
    cfg.preprocess.tile_overlap_ratio = 0.1
    cfg.detect_roi_rect = DetectROIRect(x1=0, y1=0, x2=200, y2=200)
    cfg.belt_polygon = [[0, 0], [200, 0], [200, 200], [0, 200]]
    cfg.postprocess.min_box_area_raw = 1
    cfg.postprocess.min_mask_area_raw = 1
    cfg.debug.save_debug_image = False
    counter = ParcelCounter(cfg)
    fake_backend = _FakeBackend()
    counter.backend = fake_backend

    result = counter.count_image(np.zeros((200, 200, 3), dtype=np.uint8), task_id="tile")

    assert result.code == 0
    assert fake_backend.calls == 4


class _FakeBackend:
    def __init__(self) -> None:
        self.calls = 0

    def load(self) -> None:
        pass

    def is_loaded(self) -> bool:
        return True

    def warmup(self) -> None:
        pass

    def predict(self, image_bgr: np.ndarray) -> list[Detection]:
        self.calls += 1
        return [
            Detection(
                class_id=0,
                class_name="parcel",
                score=0.9,
                box_model=[256, 256, 768, 768],
            )
        ]
