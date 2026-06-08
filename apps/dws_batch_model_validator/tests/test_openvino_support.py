from __future__ import annotations

from pathlib import Path

import pytest

from dws_validator.diagnostics import diagnose_environment
from dws_validator.predictor import detect_model_format, resolve_model_path_for_ultralytics


ROOT = Path(__file__).resolve().parents[1]


def test_pt_model_path_is_kept_for_ultralytics(tmp_path: Path):
    model = tmp_path / "parcel.pt"
    model.write_bytes(b"placeholder")

    assert detect_model_format(model) == "pt"
    assert resolve_model_path_for_ultralytics(model) == model


def test_openvino_directory_is_accepted_for_ultralytics(tmp_path: Path):
    model_dir = tmp_path / "parcel_openvino_model"
    model_dir.mkdir()
    (model_dir / "parcel.xml").write_text("<net></net>", encoding="utf-8")
    (model_dir / "parcel.bin").write_bytes(b"weights")

    assert detect_model_format(model_dir) == "openvino"
    assert resolve_model_path_for_ultralytics(model_dir) == model_dir


def test_openvino_xml_is_resolved_to_model_directory(tmp_path: Path):
    model_dir = tmp_path / "parcel_openvino_model"
    model_dir.mkdir()
    xml = model_dir / "parcel.xml"
    xml.write_text("<net></net>", encoding="utf-8")
    (model_dir / "parcel.bin").write_bytes(b"weights")

    assert detect_model_format(xml) == "openvino"
    assert resolve_model_path_for_ultralytics(xml) == model_dir


def test_openvino_xml_without_bin_has_clear_error(tmp_path: Path):
    xml = tmp_path / "parcel.xml"
    xml.write_text("<net></net>", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="OpenVINO"):
        resolve_model_path_for_ultralytics(xml)


def test_diagnose_reports_openvino_state():
    result = diagnose_environment()

    data = result.to_dict()
    assert "openvino_available" in data
    assert "openvino_version" in data


def test_gui_model_selector_mentions_openvino_xml():
    source = (ROOT / "src" / "dws_validator_gui" / "main_window.py").read_text(encoding="utf-8")

    assert "*.pt *.xml" in source
    assert "OpenVINO" in source
    assert "OpenVINO目录" in source


def test_release_files_include_openvino_dependency():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    spec = (ROOT / "packaging" / "dws_batch_model_validator.spec").read_text(encoding="utf-8")

    assert "openvino" in requirements
    assert '"openvino"' in spec
