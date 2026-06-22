from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ModelArtifact:
    backend: str
    request_path: Path
    load_path: Path
    xml_path: Path | None = None
    bin_path: Path | None = None
    metadata_path: Path | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="读取 PT、ONNX 或 OpenVINO 模型中的类别信息")
    parser.add_argument("--model", required=True, help="模型路径，支持 .pt、.onnx、OpenVINO 目录或 .xml")
    return parser.parse_args()


def _sorted_dict_items(raw_names: dict[Any, Any]) -> list[tuple[Any, Any]]:
    def sort_key(item: tuple[Any, Any]) -> tuple[int, str]:
        key = item[0]
        try:
            return (0, f"{int(key):09d}")
        except (TypeError, ValueError):
            return (1, str(key))

    return sorted(raw_names.items(), key=sort_key)


def normalize_names(raw_names: object) -> list[str]:
    if isinstance(raw_names, dict):
        return [str(value) for _key, value in _sorted_dict_items(raw_names)]
    if isinstance(raw_names, list):
        return [str(item) for item in raw_names]
    if isinstance(raw_names, str) and raw_names.strip():
        parsed = ast.literal_eval(raw_names)
        return normalize_names(parsed)
    return []


def resolve_openvino_artifact(model_path: Path) -> ModelArtifact:
    if model_path.is_dir():
        xml_files = sorted(model_path.glob("*.xml"))
        if not xml_files:
            raise FileNotFoundError(f"OpenVINO 目录缺少 .xml：{model_path}")
        if len(xml_files) != 1:
            raise ValueError(f"OpenVINO 目录只能包含 1 个 .xml：{model_path}")
        xml_path = xml_files[0]
        load_path = model_path
    else:
        xml_path = model_path
        load_path = model_path

    bin_path = xml_path.with_suffix(".bin")
    metadata_path = xml_path.parent / "metadata.yaml"
    if not bin_path.exists():
        raise FileNotFoundError(f"OpenVINO 缺少对应 .bin：{bin_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"OpenVINO 缺少 metadata.yaml：{metadata_path}")
    return ModelArtifact(
        backend="openvino",
        request_path=model_path,
        load_path=load_path,
        xml_path=xml_path,
        bin_path=bin_path,
        metadata_path=metadata_path,
    )


def resolve_model_artifact(model_path: str | Path) -> ModelArtifact:
    path = Path(model_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"模型不存在：{path}")
    suffix = path.suffix.lower()
    if path.is_dir() or suffix == ".xml":
        return resolve_openvino_artifact(path)
    if suffix == ".pt":
        return ModelArtifact(backend="pt", request_path=path, load_path=path)
    if suffix == ".onnx":
        return ModelArtifact(backend="onnx", request_path=path, load_path=path)
    raise ValueError("模型格式不支持，只支持 .pt、.onnx、OpenVINO 目录或 .xml")


def load_openvino_metadata(metadata_path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"OpenVINO metadata.yaml 内容无效：{metadata_path}")
    if "names" not in raw:
        raise ValueError(f"OpenVINO metadata.yaml 缺少 names：{metadata_path}")
    if "task" not in raw or not str(raw["task"]).strip():
        raise ValueError(f"OpenVINO metadata.yaml 缺少 task：{metadata_path}")
    return raw


def inspect_pt(model_path: Path) -> dict[str, object]:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    names = getattr(model, "names", {}) or {}
    task = getattr(model, "task", "") or getattr(getattr(model, "model", None), "task", "")
    return {
        "format": "pt",
        "task": str(task or "detect"),
        "class_names": normalize_names(names),
    }


def inspect_onnx(model_path: Path) -> dict[str, object]:
    import onnx

    model = onnx.load(str(model_path))
    metadata_props = {item.key: item.value for item in model.metadata_props}
    names = normalize_names(metadata_props.get("names", ""))
    task = str(metadata_props.get("task", "detect"))
    return {
        "format": "onnx",
        "task": task,
        "class_names": names,
        "metadata_props": metadata_props,
    }


def inspect_openvino(model_path: Path) -> dict[str, object]:
    artifact = resolve_openvino_artifact(model_path)
    assert artifact.metadata_path is not None
    metadata = load_openvino_metadata(artifact.metadata_path)
    return {
        "format": "openvino",
        "task": str(metadata["task"]).strip(),
        "class_names": normalize_names(metadata["names"]),
        "metadata": metadata,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_model_artifact(args.model)
    if artifact.backend == "pt":
        result = inspect_pt(artifact.load_path)
    elif artifact.backend == "onnx":
        result = inspect_onnx(artifact.load_path)
    else:
        result = inspect_openvino(artifact.request_path)

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
