from __future__ import annotations

from app.config import Config
from app.vision.counter import ParcelCounter


def test_health_reports_int8_metadata(tmp_path):
    model_dir = tmp_path / "best_int8_openvino_model"
    model_dir.mkdir()
    (model_dir / "metadata.yaml").write_text(
        "task: segment\nargs:\n  int8: true\n",
        encoding="utf-8",
    )
    cfg = Config()
    cfg.model.model_path = str(model_dir)

    health = ParcelCounter(cfg).health()

    assert health["model_task"] == "segment"
    assert health["model_int8"] is True
