from __future__ import annotations

import numpy as np
import pytest

from app.config import Config
from app.vision.backends.native_openvino_backend import NativeOpenVINOBackend


def test_native_backend_converts_bgr_image_to_rgb_tensor():
    backend = NativeOpenVINOBackend(Config())
    image = np.array([[[10, 20, 30]]], dtype=np.uint8)

    tensor = backend._to_input_tensor(image)

    assert tensor.shape == (1, 3, 1, 1)
    assert tensor[0, :, 0, 0].tolist() == pytest.approx([
        30 / 255.0,
        20 / 255.0,
        10 / 255.0,
    ])


def test_native_backend_parses_end2end_segmentation_outputs():
    cfg = Config()
    cfg.model.confidence_threshold = 0.4
    backend = NativeOpenVINOBackend(cfg)
    predictions = np.zeros((1, 300, 38), dtype=np.float32)
    predictions[0, 0, :6] = [10, 20, 110, 220, 0.9, 0]
    predictions[0, 0, 6] = 1.0
    predictions[0, 1, :6] = [300, 300, 500, 500, 0.1, 0]
    predictions[0, 1, 6] = 1.0
    prototypes = np.zeros((1, 32, 256, 256), dtype=np.float32)
    prototypes[0, 0, :, :] = 1.0

    detections = backend._convert_outputs(
        [predictions, prototypes],
        image_shape=(1024, 1024),
    )

    assert len(detections) == 1
    detection = detections[0]
    assert detection.class_id == 0
    assert detection.class_name == "parcel"
    assert detection.score == pytest.approx(0.9)
    assert detection.box_model == [10.0, 20.0, 110.0, 220.0]
    assert detection.mask_model is not None
    assert detection.mask_model.shape == (1024, 1024)
    assert 21_000 <= detection.mask_area_model <= 23_000
