from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config import Config
from app.schemas import CountResult
from app.vision.runner import VisionRunner
from scripts.benchmark import benchmark_image


ROOT = Path(__file__).resolve().parents[1]


def _result(task_id: str = "task") -> CountResult:
    return CountResult(
        task_id=task_id,
        code=0,
        message="ok_empty",
        parcel_count=0,
    )


def test_vision_runner_returns_current_count_result() -> None:
    counter = MagicMock()
    counter.count_bytes.return_value = _result("demo")

    with patch("app.vision.runner.ParcelCounter", return_value=counter):
        runner = VisionRunner(Config())
        result = runner.count_from_buffer(b"jpeg", task_id="demo", image_encoding="jpg")

    assert result.task_id == "demo"
    assert result.code == 0
    meta = counter.count_bytes.call_args.args[0]
    assert meta.task_id == "demo"
    assert meta.image_encoding == "jpg"


def test_runner_fixture_uses_current_backend_contract(runner: VisionRunner) -> None:
    result = runner.count_from_buffer(b"not-an-image")

    assert result.code != 0


def test_demo_script_can_start_directly() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/demo.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_benchmark_image_uses_production_byte_entry_once(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"jpeg")
    counter = MagicMock()
    counter.count_bytes.return_value = _result("sample")

    row = benchmark_image(counter, image_path)

    counter.count_bytes.assert_called_once()
    assert row["file"] == "sample.jpg"
    assert row["code"] == 0
