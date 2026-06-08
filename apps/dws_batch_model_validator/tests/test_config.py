from __future__ import annotations

import json
import sys

import pytest

from dws_validator.config import RuntimeConfig, load_config
from dws_validator.diagnostics import diagnose_environment
from dws_validator.runtime_paths import RuntimePaths


def test_default_config_loads_with_user_output_dir():
    cfg = load_config("configs/default.yaml")

    assert cfg.imgsz_h == 736
    assert cfg.imgsz_w == 960
    assert "DWSBatchModelValidator" in cfg.output_base_dir
    assert "Program Files" not in cfg.output_base_dir


def test_cli_args_override_yaml(tmp_path):
    cfg_file = tmp_path / "default.yaml"
    cfg_file.write_text(
        """
model:
  path: models/a.pt
  imgsz: [736, 960]
data:
  images: data/images
  labels: data/labels
thresholds:
  low_conf: 0.2
  high_conf: 0.6
  iou: 0.4
output:
  base_dir: outputs/runs
""",
        encoding="utf-8",
    )

    cfg = load_config(
        cfg_file,
        model="models/b.pt",
        images="custom/images",
        labels="custom/labels",
        output=str(tmp_path / "runs"),
        imgsz=[512, 768],
        device="cpu",
        low_conf=0.3,
        high_conf=0.7,
        iou=0.5,
    )

    assert cfg.model_path.endswith("models\\b.pt") or cfg.model_path.endswith("models/b.pt")
    assert cfg.imgsz_h == 512
    assert cfg.imgsz_w == 768
    assert cfg.device == "cpu"
    assert cfg.low_conf == 0.3
    assert cfg.high_conf == 0.7
    assert cfg.iou == 0.5


def test_low_conf_greater_than_high_conf_raises():
    with pytest.raises(ValueError):
        RuntimeConfig(
            model_path="model.pt",
            images_dir="images",
            labels_dir="labels",
            output_base_dir="out",
            low_conf=0.8,
            high_conf=0.7,
        )


def test_runtime_paths_and_diagnose_are_json_serializable():
    paths = RuntimePaths()
    result = diagnose_environment()
    data = json.loads(result.to_json())

    assert "DWSBatchModelValidator" in str(paths.user_data_dir)
    assert data["app_version"]
    assert "default_model_exists" in data


def test_runtime_paths_use_pyinstaller_internal_resource_dir(monkeypatch, tmp_path):
    internal_dir = tmp_path / "_internal"
    internal_dir.mkdir()
    exe_path = tmp_path / "DWSBatchModelValidator.exe"
    exe_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(internal_dir), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_path))

    paths = RuntimePaths()

    assert paths.app_dir == tmp_path
    assert paths.resource_dir == internal_dir
    assert paths.default_model_dir == internal_dir / "models"
    assert paths.bundled_config_path == internal_dir / "configs" / "default.yaml"
