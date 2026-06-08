from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.config import Config, IgnoreRegion
from app.schemas import DecodedImage
from app.vision.preprocess import Preprocessor, letterbox


def _decoded(image: np.ndarray) -> DecodedImage:
    h, w = image.shape[:2]
    return DecodedImage(task_id="t1", image_bgr=image, width=w, height=h, source_encoding="raw_bgr")


def _reduced_decoded(image: np.ndarray) -> DecodedImage:
    h, w = image.shape[:2]
    return DecodedImage(
        task_id="t1",
        image_bgr=image,
        width=w,
        height=h,
        original_width=w * 2,
        original_height=h * 2,
        decode_scale_x=0.5,
        decode_scale_y=0.5,
        source_encoding="jpg",
    )


def _legacy_process_image(cfg: Config, decoded: DecodedImage) -> np.ndarray:
    image = decoded.image_bgr
    decoded_height, decoded_width = image.shape[:2]
    original_width = decoded.original_width or decoded.width
    original_height = decoded.original_height or decoded.height
    decode_scale_x = decoded.decode_scale_x or decoded_width / original_width
    decode_scale_y = decoded.decode_scale_y or decoded_height / original_height
    rect = cfg.detect_roi_rect
    x1 = max(0, min(original_width - 1, rect.x1))
    y1 = max(0, min(original_height - 1, rect.y1))
    x2 = max(x1 + 1, min(original_width, rect.x2))
    y2 = max(y1 + 1, min(original_height, rect.y2))
    dx1 = max(0, min(decoded_width - 1, int(round(x1 * decode_scale_x))))
    dy1 = max(0, min(decoded_height - 1, int(round(y1 * decode_scale_y))))
    dx2 = max(dx1 + 1, min(decoded_width, int(round(x2 * decode_scale_x))))
    dy2 = max(dy1 + 1, min(decoded_height, int(round(y2 * decode_scale_y))))
    work = image[dy1:dy2, dx1:dx2].copy()

    if cfg.preprocess.mask_ignore_regions:
        height, width = work.shape[:2]
        for region in cfg.ignore_regions:
            ix1 = max(0, min(width, int(round((region.x1 - x1) * decode_scale_x))))
            iy1 = max(0, min(height, int(round((region.y1 - y1) * decode_scale_y))))
            ix2 = max(0, min(width, int(round((region.x2 - x1) * decode_scale_x))))
            iy2 = max(0, min(height, int(round((region.y2 - y1) * decode_scale_y))))
            if ix2 > ix1 and iy2 > iy1:
                work[iy1:iy2, ix1:ix2] = 0

    if cfg.preprocess.mask_outside_polygon:
        mask = np.zeros(work.shape[:2], dtype=np.uint8)
        polygon = np.array(
            [
                [
                    int(round((x - x1) * decode_scale_x)),
                    int(round((y - y1) * decode_scale_y)),
                ]
                for x, y in cfg.belt_polygon
            ],
            dtype=np.int32,
        ).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [polygon], 255)
        work[mask == 0] = 0

    return letterbox(work, cfg.preprocess.infer_imgsz, (0, 0, 0))[0]


def test_letterbox_output_size():
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    output, scale, pad_x, pad_y = letterbox(image, 1024)
    assert output.shape == (1024, 1024, 3)
    assert scale == pytest.approx(1024 / 200)
    assert pad_x == 0
    assert pad_y > 0


def test_letterbox_uses_copy_make_border(monkeypatch):
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    border_calls = 0
    original_copy_make_border = cv2.copyMakeBorder

    def counting_copy_make_border(*args, **kwargs):
        nonlocal border_calls
        border_calls += 1
        return original_copy_make_border(*args, **kwargs)

    monkeypatch.setattr(cv2, "copyMakeBorder", counting_copy_make_border)
    letterbox(image, 1024)

    assert border_calls == 1


def test_preprocess_outputs_1024_and_metadata():
    cfg = Config()
    image = np.full((3036, 4024, 3), 255, dtype=np.uint8)
    output = Preprocessor(cfg).process(_decoded(image))
    assert output.model_input_image.shape == (1024, 1024, 3)
    assert output.scale > 0
    assert output.pad_x >= 0
    assert output.pad_y >= 0
    assert output.roi_rect == [355, 0, 3540, 2595]
    assert output.original_shape == (3036, 4024)


def test_osd_region_masked_before_roi():
    cfg = Config()
    image = np.full((3036, 4024, 3), 255, dtype=np.uint8)
    output = Preprocessor(cfg).process(_decoded(image))
    x_model = int((500 - output.roi_rect[0]) * output.scale + output.pad_x)
    y_model = int(100 * output.scale + output.pad_y)
    assert np.all(output.model_input_image[y_model, x_model] == 0)


def test_polygon_outside_masked_before_roi():
    cfg = Config()
    image = np.full((3036, 4024, 3), 255, dtype=np.uint8)
    output = Preprocessor(cfg).process(_decoded(image))
    x_model = int((400 - output.roi_rect[0]) * output.scale + output.pad_x)
    y_model = int(2400 * output.scale + output.pad_y)
    assert np.all(output.model_input_image[y_model, x_model] == 0)


def test_reduced_decode_uses_original_roi_coordinates():
    cfg = Config()
    image = np.full((1518, 2012, 3), 255, dtype=np.uint8)
    output = Preprocessor(cfg).process(_reduced_decoded(image))
    assert output.model_input_image.shape == (1024, 1024, 3)
    assert output.roi_rect == [355, 0, 3540, 2595]
    assert output.original_shape == (3036, 4024)
    assert output.scale == pytest.approx(1024 / (3540 - 355), rel=0.01)


@pytest.mark.parametrize("reduced", [False, True])
def test_optimized_preprocess_is_pixel_identical_to_legacy(reduced: bool):
    cfg = Config()
    cfg.ignore_regions = [
        IgnoreRegion(name="osd_text", x1=0, y1=0, x2=1250, y2=460)
    ]
    rng = np.random.default_rng(42)
    shape = (1518, 2012, 3) if reduced else (3036, 4024, 3)
    image = rng.integers(0, 256, shape, dtype=np.uint8)
    decoded = _reduced_decoded(image) if reduced else _decoded(image)

    expected = _legacy_process_image(cfg, decoded)
    actual = Preprocessor(cfg).process(decoded).model_input_image

    assert np.array_equal(actual, expected)


def test_preprocessor_reuses_combined_mask(monkeypatch):
    cfg = Config()
    cfg.ignore_regions = [
        IgnoreRegion(name="osd_text", x1=0, y1=0, x2=1250, y2=460)
    ]
    image = np.full((3036, 4024, 3), 255, dtype=np.uint8)
    preprocessor = Preprocessor(cfg)
    fill_calls = 0
    original_fill_poly = cv2.fillPoly

    def counting_fill_poly(*args, **kwargs):
        nonlocal fill_calls
        fill_calls += 1
        return original_fill_poly(*args, **kwargs)

    monkeypatch.setattr(cv2, "fillPoly", counting_fill_poly)
    preprocessor.process(_decoded(image))
    preprocessor.process(_decoded(image))

    assert fill_calls == 1


def test_preprocessor_applies_mask_with_copy_to(monkeypatch):
    cfg = Config()
    cfg.ignore_regions = [
        IgnoreRegion(name="osd_text", x1=0, y1=0, x2=1250, y2=460)
    ]
    image = np.full((3036, 4024, 3), 255, dtype=np.uint8)
    copy_calls = 0
    original_copy_to = cv2.copyTo

    def counting_copy_to(*args, **kwargs):
        nonlocal copy_calls
        copy_calls += 1
        return original_copy_to(*args, **kwargs)

    monkeypatch.setattr(cv2, "copyTo", counting_copy_to)
    Preprocessor(cfg).process(_decoded(image))

    assert copy_calls == 1
