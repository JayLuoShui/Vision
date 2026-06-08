from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Config
from app.windows_settings import IgnoreRectDraft, SettingsDraft, build_config


def _draft(model_path: Path) -> SettingsDraft:
    return SettingsDraft(
        tcp_port=9200,
        model_path=str(model_path),
        confidence_threshold=0.55,
        iou_threshold=0.60,
        inference_num_threads=6,
        decode_reduce_factor=2,
        save_debug_image=True,
        image_width=1920,
        image_height=1080,
        detect_roi_rect=(100, 80, 1800, 1000),
        belt_polygon=((200, 100), (1700, 100), (1750, 950), (150, 950)),
        ignore_regions=(
            IgnoreRectDraft("osd", 0, 0, 500, 120),
        ),
    )


def test_build_config_applies_settings_without_mutating_running_config(tmp_path):
    model_path = tmp_path / "model"
    model_path.mkdir()
    current = Config()

    updated = build_config(current, _draft(model_path), app_root=tmp_path)

    assert updated is not current
    assert current.service.tcp_port == 9100
    assert updated.service.tcp_port == 9200
    assert updated.model.confidence_threshold == 0.55
    assert updated.model.iou_threshold == 0.60
    assert updated.model.inference_num_threads == 6
    assert updated.service.decode_reduce_factor == 2
    assert updated.debug.save_debug_image is True
    assert updated.camera.raw_width == 1920
    assert updated.camera.raw_height == 1080
    assert updated.get_roi_rect() == (100, 80, 1800, 1000)
    assert updated.belt_polygon[0] == [200, 100]
    assert updated.ignore_regions[0].name == "osd"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tcp_port", 0),
        ("tcp_port", 70000),
        ("confidence_threshold", -0.01),
        ("confidence_threshold", 1.01),
        ("iou_threshold", -0.01),
        ("iou_threshold", 1.01),
        ("inference_num_threads", 0),
        ("decode_reduce_factor", 3),
    ],
)
def test_build_config_rejects_invalid_runtime_values(tmp_path, field, value):
    model_path = tmp_path / "model"
    model_path.mkdir()
    values = _draft(model_path).__dict__ | {field: value}

    with pytest.raises(ValueError):
        build_config(Config(), SettingsDraft(**values), app_root=tmp_path)


def test_build_config_rejects_missing_model(tmp_path):
    with pytest.raises(ValueError, match="模型"):
        build_config(Config(), _draft(tmp_path / "missing"), app_root=tmp_path)


def test_build_config_rejects_self_intersecting_belt_polygon(tmp_path):
    model_path = tmp_path / "model"
    model_path.mkdir()
    draft = _draft(model_path)
    values = draft.__dict__ | {
        "belt_polygon": ((100, 100), (800, 800), (100, 800), (800, 100))
    }

    with pytest.raises(ValueError, match="自相交"):
        build_config(Config(), SettingsDraft(**values), app_root=tmp_path)


def test_build_config_rejects_zero_area_belt_polygon(tmp_path):
    model_path = tmp_path / "model"
    model_path.mkdir()
    draft = _draft(model_path)
    values = draft.__dict__ | {
        "belt_polygon": ((100, 100), (200, 200), (300, 300))
    }

    with pytest.raises(ValueError, match="面积"):
        build_config(Config(), SettingsDraft(**values), app_root=tmp_path)


def test_build_config_rejects_roi_outside_selected_image(tmp_path):
    model_path = tmp_path / "model"
    model_path.mkdir()
    draft = _draft(model_path)
    values = draft.__dict__ | {"detect_roi_rect": (100, 80, 2000, 1000)}

    with pytest.raises(ValueError, match="检测区域"):
        build_config(Config(), SettingsDraft(**values), app_root=tmp_path)
