from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSPECTOR_PATH = ROOT / "apps" / "cvds_cpp_detector" / "scripts" / "inspect_model_metadata.py"


def load_module(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    extra_modules: dict[str, object] | None = None,
):
    modules = dict(extra_modules or {})
    for name, value in modules.items():
        monkeypatch.setitem(sys.modules, name, value)
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, INSPECTOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_openvino_bundle(path: Path, *, with_metadata: bool = True) -> tuple[Path, Path]:
    path.mkdir(parents=True, exist_ok=True)
    xml_path = path / "demo.xml"
    xml_path.write_text("<xml />", encoding="utf-8")
    (path / "demo.bin").write_bytes(b"bin")
    if with_metadata:
        (path / "metadata.yaml").write_text(
            json.dumps({"task": "detect", "names": {"0": "parcel"}}, ensure_ascii=False),
            encoding="utf-8",
        )
    return path, xml_path


def test_inspector_reads_openvino_metadata_from_directory_and_xml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load_module(monkeypatch, "inspect_model_metadata_test_openvino")
    openvino_dir, xml_path = write_openvino_bundle(tmp_path / "demo_openvino_model")

    monkeypatch.setattr(sys, "argv", ["inspect_model_metadata.py", "--model", str(openvino_dir)])
    assert module.main() == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["format"] == "openvino"
    assert payload["task"] == "detect"
    assert payload["class_names"] == ["parcel"]

    monkeypatch.setattr(sys, "argv", ["inspect_model_metadata.py", "--model", str(xml_path)])
    assert module.main() == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["format"] == "openvino"
    assert payload["class_names"] == ["parcel"]


def test_inspector_rejects_openvino_bundle_missing_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module(monkeypatch, "inspect_model_metadata_test_openvino_missing")
    openvino_dir, _xml_path = write_openvino_bundle(tmp_path / "broken_openvino_model", with_metadata=False)

    monkeypatch.setattr(sys, "argv", ["inspect_model_metadata.py", "--model", str(openvino_dir)])
    with pytest.raises(FileNotFoundError, match="metadata.yaml"):
        module.main()


def test_inspector_reads_pt_and_onnx_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_onnx = types.SimpleNamespace(
        load=lambda _path: types.SimpleNamespace(
            metadata_props=[
                types.SimpleNamespace(key="names", value="{0: 'parcel'}"),
                types.SimpleNamespace(key="task", value="detect"),
            ]
        )
    )
    fake_ultralytics = types.SimpleNamespace(
        YOLO=lambda _path: types.SimpleNamespace(names={0: "parcel"}, task="detect")
    )
    module = load_module(
        monkeypatch,
        "inspect_model_metadata_test_common_formats",
        extra_modules={"onnx": fake_onnx, "ultralytics": fake_ultralytics},
    )

    pt_path = tmp_path / "model.pt"
    onnx_path = tmp_path / "model.onnx"
    pt_path.write_text("stub", encoding="utf-8")
    onnx_path.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["inspect_model_metadata.py", "--model", str(pt_path)])
    assert module.main() == 0
    assert json.loads(capsys.readouterr().out.strip())["format"] == "pt"

    monkeypatch.setattr(sys, "argv", ["inspect_model_metadata.py", "--model", str(onnx_path)])
    assert module.main() == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["format"] == "onnx"
    assert payload["class_names"] == ["parcel"]
