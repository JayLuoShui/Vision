from __future__ import annotations

import csv
import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "apps" / "cvds_cpp_detector" / "scripts"
PT_MONITOR_PATH = SCRIPTS_DIR / "pt_video_flow_monitor.py"
WORKER_ENTRY_PATH = SCRIPTS_DIR / "worker_entry.py"


class FakeTensor:
    def __init__(self, value: list[list[float]] | list[float] | list[int]) -> None:
        self._array = np.array(value)

    def cpu(self) -> "FakeTensor":
        return self

    def numpy(self) -> np.ndarray:
        return self._array


class FakeBoxes:
    def __init__(self, items: list[dict[str, float | int]]) -> None:
        self._items = items
        self.xyxy = FakeTensor([[item["x1"], item["y1"], item["x2"], item["y2"]] for item in items])
        self.conf = FakeTensor([item["conf"] for item in items])
        self.cls = FakeTensor([item["cls"] for item in items])
        self.id = FakeTensor([item["track_id"] for item in items])

    def __len__(self) -> int:
        return len(self._items)


class FakeResult:
    def __init__(self, items: list[dict[str, float | int]]) -> None:
        self.boxes = FakeBoxes(items)
        self.names = {0: "parcel"}


class FakeYOLO:
    def __init__(self, _weights: str, frames: list[list[dict[str, float | int]]]) -> None:
        self._frames = frames
        self._index = 0

    def track(self, *_args, **_kwargs) -> list[FakeResult]:
        frame_items = self._frames[self._index] if self._index < len(self._frames) else []
        self._index += 1
        return [FakeResult(frame_items)]


class FakeCapture:
    def __init__(
        self,
        frames: list[np.ndarray],
        fps: float,
        *,
        opened: bool = True,
        fail_read_after: int | None = None,
    ) -> None:
        self._frames = frames
        self._fps = fps
        self._index = 0
        self._height, self._width = frames[0].shape[:2]
        self._opened = opened
        self._fail_read_after = fail_read_after
        self.released = False

    def isOpened(self) -> bool:
        return self._opened

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._opened:
            return False, None
        if self._fail_read_after is not None and self._index >= self._fail_read_after:
            return False, None
        if self._index >= len(self._frames):
            return False, None
        frame = self._frames[self._index]
        self._index += 1
        return True, frame.copy()

    def get(self, prop: int) -> float:
        if prop == 5:
            return self._fps
        if prop == 3:
            return float(self._width)
        if prop == 4:
            return float(self._height)
        return 0.0

    def release(self) -> None:
        self.released = True


class FakeWriter:
    def __init__(self, opened: bool = True) -> None:
        self.frames: list[np.ndarray] = []
        self.opened = opened
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def write(self, frame: np.ndarray) -> None:
        self.frames.append(frame.copy())

    def release(self) -> None:
        self.released = True


class FakeCv2(types.SimpleNamespace):
    CAP_FFMPEG = 1900
    CAP_PROP_FPS = 5
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_PROP_OPEN_TIMEOUT_MSEC = 53
    CAP_PROP_READ_TIMEOUT_MSEC = 54
    IMWRITE_JPEG_QUALITY = 1
    FONT_HERSHEY_SIMPLEX = 0
    LINE_AA = 16

    def __init__(
        self,
        frames: list[np.ndarray],
        fps: float,
        *,
        capture_opened: bool = True,
        fail_read_after: int | None = None,
    ) -> None:
        super().__init__()
        self._frames = frames
        self._fps = fps
        self._capture_opened = capture_opened
        self._fail_read_after = fail_read_after
        self.capture: FakeCapture | None = None
        self.video_capture_calls: list[tuple[object, ...]] = []
        self.writers: list[FakeWriter] = []

    def imencode(self, _ext: str, image: np.ndarray, _params: list[int]) -> tuple[bool, np.ndarray]:
        return True, np.array(image.flatten()[:16], dtype=np.uint8)

    def VideoCapture(self, *args) -> FakeCapture:
        self.video_capture_calls.append(args)
        self.capture = FakeCapture(
            self._frames,
            self._fps,
            opened=self._capture_opened,
            fail_read_after=self._fail_read_after,
        )
        return self.capture

    def VideoWriter(self, *_args) -> FakeWriter:
        writer = FakeWriter()
        self.writers.append(writer)
        return writer

    def VideoWriter_fourcc(self, *_args) -> int:
        return 0

    def pointPolygonTest(self, contour: np.ndarray, point: tuple[float, float], _measure_dist: bool) -> float:
        x = float(point[0])
        y = float(point[1])
        points = [(float(px), float(py)) for px, py in contour.tolist()]
        inside = False
        count = len(points)
        for index in range(count):
            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % count]
            if ((y1 > y) != (y2 > y)) and (x < ((x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1)):
                inside = not inside
        return 1.0 if inside else -1.0

    def boundingRect(self, contour: np.ndarray) -> tuple[int, int, int, int]:
        xs = contour[:, 0]
        ys = contour[:, 1]
        x1 = int(xs.min())
        y1 = int(ys.min())
        x2 = int(xs.max())
        y2 = int(ys.max())
        return x1, y1, x2 - x1 + 1, y2 - y1 + 1

    def polylines(self, _frame: np.ndarray, _pts, _is_closed: bool, _color, _thickness: int) -> None:
        return None

    def putText(self, _frame: np.ndarray, _text: str, _origin: tuple[int, int], *_args) -> None:
        return None

    def rectangle(self, _frame: np.ndarray, _pt1: tuple[int, int], _pt2: tuple[int, int], _color, _thickness: int) -> None:
        return None

    def line(self, _frame: np.ndarray, _p1: tuple[int, int], _p2: tuple[int, int], _color, _thickness: int) -> None:
        return None

    def addWeighted(
        self,
        frame_a: np.ndarray,
        alpha: float,
        frame_b: np.ndarray,
        beta: float,
        gamma: float,
    ) -> np.ndarray:
        result = frame_a.astype(np.float32) * alpha + frame_b.astype(np.float32) * beta + gamma
        return np.clip(result, 0, 255).astype(np.uint8)


def load_module(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    path: Path,
    extra_modules: dict[str, object] | None = None,
):
    modules: dict[str, object] = {
        "torch": types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False)),
        "cv2": FakeCv2([np.zeros((8, 8, 3), dtype=np.uint8)], fps=2.0),
        "ultralytics": types.SimpleNamespace(YOLO=lambda weights: FakeYOLO(weights, [[]])),
    }
    modules.update(extra_modules or {})
    for name, value in modules.items():
        monkeypatch.setitem(sys.modules, name, value)
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_worker_diagnose_requires_all_supported_model_backends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_torch = types.SimpleNamespace(
        __version__="2.11.0",
        version=types.SimpleNamespace(cuda="12.8"),
        cuda=types.SimpleNamespace(
            is_available=lambda: False,
            get_device_name=lambda _index: "",
        ),
    )
    worker = load_module(
        monkeypatch,
        "worker_entry_test_backend_diagnose",
        WORKER_ENTRY_PATH,
        extra_modules={"torch": fake_torch},
    )
    monkeypatch.setattr(
        worker,
        "query_nvidia_smi",
        lambda: {
            "available": False,
            "gpu_name": "",
            "driver_version": "",
            "error": "未找到 nvidia-smi。",
        },
    )

    availability = {
        "ultralytics": True,
        "cv2": True,
        "PIL": True,
        "numpy": True,
        "onnx": True,
        "onnxruntime": True,
        "openvino": True,
    }
    monkeypatch.setattr(
        worker,
        "import_status",
        lambda module_name: (availability[module_name], "" if availability[module_name] else "missing"),
    )

    diagnostics = worker.collect_runtime_diagnostics()

    assert diagnostics["onnx_available"] is True
    assert diagnostics["onnxruntime_available"] is True
    assert diagnostics["openvino_available"] is True
    assert worker.diagnose() == 0

    availability["onnxruntime"] = False
    diagnostics = worker.collect_runtime_diagnostics()

    assert diagnostics["onnxruntime_available"] is False
    assert worker.diagnose() == 1


def write_regions(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "total_count_region": "main",
                "regions": [
                    {
                        "id": "main",
                        "name": "主线入口",
                        "polygon": [[0, 0], [40, 0], [40, 40], [0, 40]],
                        "count_enabled": True,
                        "jam_enabled": False,
                        "jam_seconds": 1,
                        "priority": 1,
                    },
                    {
                        "id": "branch",
                        "name": "右分流口",
                        "polygon": [[10, 10], [30, 10], [30, 30], [10, 30]],
                        "count_enabled": True,
                        "jam_enabled": True,
                        "jam_seconds": 1,
                        "priority": 2,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def write_openvino_model_bundle(path: Path, *, task: str = "detect") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    model_path = path / "demo.xml"
    model_path.write_text("<xml />", encoding="utf-8")
    (path / "demo.bin").write_bytes(b"bin")
    (path / "metadata.yaml").write_text(
        json.dumps({"task": task, "names": {"0": "parcel"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_load_regions_strict_validation_and_legacy_roi(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = load_module(monkeypatch, "pt_video_flow_monitor_test_schema", PT_MONITOR_PATH)

    invalid_path = tmp_path / "invalid_regions.json"
    invalid_path.write_text(
        json.dumps({"version": 1, "regions": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="total_count_region"):
        module.load_regions(invalid_path)

    config = module.load_regions(write_regions(tmp_path / "regions.json"))
    assert config.total_count_region == "main"
    assert [region.id for region in config.regions] == ["main", "branch"]

    bom_path = tmp_path / "regions_bom.json"
    bom_path.write_text(
        (tmp_path / "regions.json").read_text(encoding="utf-8"),
        encoding="utf-8-sig",
    )
    assert module.load_regions(bom_path).total_count_region == "main"

    unsupported_path = write_regions(tmp_path / "unsupported_regions.json")
    unsupported = json.loads(unsupported_path.read_text(encoding="utf-8"))
    unsupported["version"] = 2
    unsupported_path.write_text(json.dumps(unsupported, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        module.load_regions(unsupported_path)

    legacy = module.build_single_region_from_legacy_roi("0,0,10,0,10,10", jam_seconds=3)
    assert legacy.total_count_region == "default"
    assert legacy.regions[0].name == "流量区域"
    assert legacy.regions[0].jam_seconds == 3


def test_draw_text_renders_chinese_region_name(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module(monkeypatch, "pt_video_flow_monitor_test_chinese_text", PT_MONITOR_PATH)
    frame = np.zeros((80, 320, 3), dtype=np.uint8)

    module.draw_text(frame, "主线入口", (12, 42))

    assert int(frame.sum()) > 0


def test_worker_entry_supports_regions_and_rejects_missing_roi_and_regions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    forwarded: dict[str, list[str]] = {}

    fake_monitor = types.SimpleNamespace(main=lambda: forwarded.setdefault("argv", list(sys.argv)))
    monkeypatch.setitem(sys.modules, "pt_video_flow_monitor", fake_monitor)
    worker = load_module(monkeypatch, "worker_entry_test_multi_roi", WORKER_ENTRY_PATH)

    model = tmp_path / "model.pt"
    tracker = tmp_path / "tracker.yaml"
    regions = write_regions(tmp_path / "regions.json")
    output_dir = tmp_path / "out"
    preview_path = tmp_path / "preview.jpg"
    jam_path = tmp_path / "jam.jsonl"
    model.write_text("stub", encoding="utf-8")
    tracker.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_entry.py",
            "detect",
            "--model",
            str(model),
            "--source",
            "demo.mp4",
            "--output-dir",
            str(output_dir),
            "--preview-path",
            str(preview_path),
            "--regions",
            str(regions),
            "--tracker",
            str(tracker),
            "--jam-signal-path",
            str(jam_path),
        ],
    )
    assert worker.main() == 0
    assert "--regions" in forwarded["argv"]
    assert "--roi" not in forwarded["argv"]

    forwarded.clear()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_entry.py",
            "detect",
            "--model",
            str(model),
            "--source",
            "demo.mp4",
            "--output-dir",
            str(output_dir),
            "--preview-path",
            str(preview_path),
            "--tracker",
            str(tracker),
            "--jam-signal-path",
            str(jam_path),
        ],
    )
    assert worker.main() == 2
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["type"] == "error"
    assert "roi" in payload["message"].lower()
    assert "regions" in payload["message"].lower()


def test_multi_roi_worker_outputs_region_protocol_and_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    frames = [np.zeros((48, 48, 3), dtype=np.uint8) for _ in range(4)]
    fake_cv2 = FakeCv2(frames, fps=2.0)
    track_frames = [
        [{"x1": 12, "y1": 12, "x2": 20, "y2": 20, "conf": 0.95, "cls": 0, "track_id": 7}],
        [{"x1": 12, "y1": 12, "x2": 20, "y2": 20, "conf": 0.95, "cls": 0, "track_id": 7}],
        [{"x1": 12, "y1": 12, "x2": 20, "y2": 20, "conf": 0.95, "cls": 0, "track_id": 7}],
        [],
    ]
    module = load_module(
        monkeypatch,
        "pt_video_flow_monitor_test_runtime",
        PT_MONITOR_PATH,
        extra_modules={
            "cv2": fake_cv2,
            "ultralytics": types.SimpleNamespace(YOLO=lambda weights: FakeYOLO(weights, track_frames)),
        },
    )

    model = tmp_path / "model.pt"
    model.write_text("stub", encoding="utf-8")
    output_dir = tmp_path / "out"
    preview_path = tmp_path / "preview.jpg"
    regions_path = write_regions(tmp_path / "regions.json")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pt_video_flow_monitor.py",
            "--model",
            str(model),
            "--source",
            "demo.mp4",
            "--output-dir",
            str(output_dir),
            "--preview-path",
            str(preview_path),
            "--regions",
            str(regions_path),
            "--tracker",
            "bytetrack.yaml",
            "--jam-seconds",
            "1",
        ],
    )

    module.main()

    payloads = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    frame_payloads = [payload for payload in payloads if payload["type"] == "frame"]
    jam_payloads = [payload for payload in payloads if payload["type"] == "jam"]
    done_payload = payloads[-1]

    assert frame_payloads[-1]["total_count"] == 1
    assert frame_payloads[-1]["flow_count"] == 1
    assert frame_payloads[-1]["inside_count"] == 0
    assert frame_payloads[-1]["global_status"] == "IDLE"
    assert frame_payloads[-1]["jam_active"] is False
    assert [region["id"] for region in frame_payloads[-1]["regions"]] == ["main", "branch"]
    assert frame_payloads[-1]["regions"][0]["status"] == "IDLE"
    assert frame_payloads[-1]["regions"][1]["status"] == "IDLE"
    assert all(
        region["stale_seconds"] == 0.0
        for payload in frame_payloads
        for region in payload["regions"]
        if not region["jam_active"]
    )

    assert jam_payloads == [
        {
            "type": "jam",
            "event_type": "jam_detected",
            "timestamp_ms": jam_payloads[0]["timestamp_ms"],
            "frame": 3,
            "region_id": "branch",
            "region_name": "右分流口",
            "flow_count": 1,
            "inside_count": 1,
            "jam_count": 1,
            "stale_seconds": 1.0,
            "signal": "IO_JAM_ON",
        },
        {
            "type": "jam",
            "event_type": "jam_cleared",
            "timestamp_ms": jam_payloads[1]["timestamp_ms"],
            "frame": 4,
            "region_id": "branch",
            "region_name": "右分流口",
            "flow_count": 1,
            "inside_count": 0,
            "jam_count": 1,
            "stale_seconds": 1.5,
            "signal": "IO_JAM_OFF",
        },
    ]

    assert done_payload["type"] == "done"
    assert done_payload["frames"] == 4
    assert done_payload["total_count_region"] == "main"
    assert done_payload["total_count"] == 1
    assert done_payload["flow_count"] == 1
    assert done_payload["global_jam_count"] == 1
    assert done_payload["jam_count"] == 1
    assert [region["id"] for region in done_payload["regions"]] == ["main", "branch"]

    with (output_dir / "flow_events.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["region_id"] == "main"
    assert rows[0]["region_name"] == "主线入口"
    assert rows[0]["region_flow_count"] == "1"
    assert rows[1]["region_id"] == "branch"

    jam_lines = [
        json.loads(line)
        for line in (output_dir / "jam_signals.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [line["signal"] for line in jam_lines] == ["IO_JAM_ON", "IO_JAM_OFF"]
    assert all(line["region_id"] == "branch" for line in jam_lines)
    assert all(line["region_name"] == "右分流口" for line in jam_lines)

    summary = json.loads((output_dir / "flow_summary.json").read_text(encoding="utf-8"))
    assert summary["total_count_region"] == "main"
    assert summary["regions"][1]["jam_count"] == 1

    jam_frame = fake_cv2.writers[0].frames[2]
    assert int(jam_frame[0, 0, 2]) > int(jam_frame[0, 0, 1])
    assert preview_path.exists()


def test_jam_timer_starts_when_non_counting_region_becomes_occupied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    frames = [np.zeros((48, 48, 3), dtype=np.uint8) for _ in range(7)]
    fake_cv2 = FakeCv2(frames, fps=2.0)
    track_frames = [
        [],
        [],
        [],
        [],
        [{"x1": 12, "y1": 12, "x2": 20, "y2": 20, "conf": 0.95, "cls": 0, "track_id": 9}],
        [{"x1": 12, "y1": 12, "x2": 20, "y2": 20, "conf": 0.95, "cls": 0, "track_id": 9}],
        [{"x1": 12, "y1": 12, "x2": 20, "y2": 20, "conf": 0.95, "cls": 0, "track_id": 9}],
    ]
    module = load_module(
        monkeypatch,
        "pt_video_flow_monitor_test_occupancy_timer",
        PT_MONITOR_PATH,
        extra_modules={
            "cv2": fake_cv2,
            "ultralytics": types.SimpleNamespace(YOLO=lambda weights: FakeYOLO(weights, track_frames)),
        },
    )

    model = tmp_path / "model.pt"
    model.write_text("stub", encoding="utf-8")
    regions_path = write_regions(tmp_path / "regions.json")
    config = json.loads(regions_path.read_text(encoding="utf-8"))
    config["regions"][1]["count_enabled"] = False
    regions_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pt_video_flow_monitor.py",
            "--model",
            str(model),
            "--source",
            "demo.mp4",
            "--output-dir",
            str(tmp_path / "out"),
            "--preview-path",
            str(tmp_path / "preview.jpg"),
            "--regions",
            str(regions_path),
            "--tracker",
            "bytetrack.yaml",
        ],
    )

    module.main()

    payloads = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    detected = [payload for payload in payloads if payload.get("event_type") == "jam_detected"]
    assert len(detected) == 1
    assert detected[0]["region_id"] == "branch"
    assert detected[0]["frame"] == 7


def test_worker_entry_reports_monitor_import_failure_as_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    worker = load_module(monkeypatch, "worker_entry_test_import_failure", WORKER_ENTRY_PATH)
    model = tmp_path / "model.pt"
    tracker = tmp_path / "tracker.yaml"
    regions = write_regions(tmp_path / "regions.json")
    model.write_text("stub", encoding="utf-8")
    tracker.write_text("stub", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "pt_video_flow_monitor", None)
    args = types.SimpleNamespace(
        model=str(model),
        tracker=str(tracker),
        regions=str(regions),
        roi=None,
        output_dir=str(tmp_path / "out"),
        device="cpu",
        source="demo.mp4",
        preview_path=str(tmp_path / "preview.jpg"),
        conf=0.25,
        iou=0.45,
        imgsz=640,
        class_id=-1,
        preview_fps=10,
        jam_seconds=3,
        jam_signal_path=str(tmp_path / "jam.jsonl"),
        max_frames=0,
        detect_roi=None,
        rtsp_transport="tcp",
    )

    assert worker.detect(args) == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["type"] == "error"
    assert "pt_video_flow_monitor" in payload["message"]


def test_active_jam_is_cleared_when_video_ends(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    frames = [np.zeros((48, 48, 3), dtype=np.uint8) for _ in range(3)]
    fake_cv2 = FakeCv2(frames, fps=2.0)
    tracked = [[{"x1": 12, "y1": 12, "x2": 20, "y2": 20, "conf": 0.95, "cls": 0, "track_id": 9}]] * 3
    module = load_module(
        monkeypatch,
        "pt_video_flow_monitor_test_final_jam_clear",
        PT_MONITOR_PATH,
        extra_modules={
            "cv2": fake_cv2,
            "ultralytics": types.SimpleNamespace(YOLO=lambda weights: FakeYOLO(weights, tracked)),
        },
    )
    model = tmp_path / "model.pt"
    model.write_text("stub", encoding="utf-8")
    regions_path = write_regions(tmp_path / "regions.json")
    config = json.loads(regions_path.read_text(encoding="utf-8"))
    config["regions"][0]["jam_seconds"] = 1
    regions_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pt_video_flow_monitor.py",
            "--model",
            str(model),
            "--source",
            "demo.mp4",
            "--output-dir",
            str(output_dir),
            "--preview-path",
            str(tmp_path / "preview.jpg"),
            "--regions",
            str(regions_path),
        ],
    )

    module.main()

    payloads = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    jam_events = [payload for payload in payloads if payload.get("type") == "jam"]
    assert [payload["signal"] for payload in jam_events] == ["IO_JAM_ON", "IO_JAM_OFF"]
    assert jam_events[-1]["reason"] == "monitor_stopped"


def test_rtsp_read_failure_is_not_reported_as_normal_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frames = [np.zeros((48, 48, 3), dtype=np.uint8)]
    fake_cv2 = FakeCv2(frames, fps=2.0)
    module = load_module(
        monkeypatch,
        "pt_video_flow_monitor_test_rtsp_disconnect",
        PT_MONITOR_PATH,
        extra_modules={
            "cv2": fake_cv2,
            "ultralytics": types.SimpleNamespace(YOLO=lambda weights: FakeYOLO(weights, [[]])),
        },
    )
    model = tmp_path / "model.pt"
    model.write_text("stub", encoding="utf-8")
    regions_path = write_regions(tmp_path / "regions.json")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pt_video_flow_monitor.py",
            "--model",
            str(model),
            "--source",
            "rtsp://camera/live",
            "--output-dir",
            str(tmp_path / "out"),
            "--preview-path",
            str(tmp_path / "preview.jpg"),
            "--regions",
            str(regions_path),
        ],
    )

    with pytest.raises(RuntimeError, match="视频流读取中断"):
        module.main()


def test_capture_is_released_when_video_writer_cannot_open(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_cv2 = FakeCv2([np.zeros((48, 48, 3), dtype=np.uint8)], fps=2.0)

    def closed_writer(*_args) -> FakeWriter:
        writer = FakeWriter(opened=False)
        fake_cv2.writers.append(writer)
        return writer

    fake_cv2.VideoWriter = closed_writer
    module = load_module(
        monkeypatch,
        "pt_video_flow_monitor_test_writer_failure",
        PT_MONITOR_PATH,
        extra_modules={"cv2": fake_cv2},
    )
    model = tmp_path / "model.pt"
    model.write_text("stub", encoding="utf-8")
    regions_path = write_regions(tmp_path / "regions.json")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pt_video_flow_monitor.py",
            "--model",
            str(model),
            "--source",
            "demo.mp4",
            "--output-dir",
            str(tmp_path / "out"),
            "--preview-path",
            str(tmp_path / "preview.jpg"),
            "--regions",
            str(regions_path),
        ],
    )

    with pytest.raises(RuntimeError, match="无法写入结果视频"):
        module.main()

    assert fake_cv2.capture is not None
    assert fake_cv2.capture.released


def test_worker_entry_rejects_unavailable_pt_gpu_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    forwarded: dict[str, list[str]] = {}

    fake_monitor = types.SimpleNamespace(main=lambda: forwarded.setdefault("argv", list(sys.argv)))
    monkeypatch.setitem(sys.modules, "pt_video_flow_monitor", fake_monitor)
    worker = load_module(monkeypatch, "worker_entry_test_pt_device_strict", WORKER_ENTRY_PATH)

    model = tmp_path / "model.pt"
    tracker = tmp_path / "tracker.yaml"
    regions = write_regions(tmp_path / "regions.json")
    model.write_text("stub", encoding="utf-8")
    tracker.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_entry.py",
            "detect",
            "--model",
            str(model),
            "--source",
            "demo.mp4",
            "--output-dir",
            str(tmp_path / "out"),
            "--preview-path",
            str(tmp_path / "preview.jpg"),
            "--regions",
            str(regions),
            "--tracker",
            str(tracker),
            "--jam-signal-path",
            str(tmp_path / "jam.jsonl"),
            "--device",
            "0",
        ],
    )

    assert worker.main() == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["type"] == "error"
    assert "cuda" in payload["message"].lower()
    assert forwarded == {}


def test_worker_entry_rejects_openvino_device_and_bundle_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_monitor = types.SimpleNamespace(main=lambda: None)
    monkeypatch.setitem(sys.modules, "pt_video_flow_monitor", fake_monitor)
    worker = load_module(monkeypatch, "worker_entry_test_openvino_device_strict", WORKER_ENTRY_PATH)

    openvino_dir = write_openvino_model_bundle(tmp_path / "good_openvino_model")
    tracker = tmp_path / "tracker.yaml"
    regions = write_regions(tmp_path / "regions.json")
    tracker.write_text("stub", encoding="utf-8")
    monkeypatch.setitem(
        sys.modules,
        "openvino.runtime",
        types.SimpleNamespace(Core=lambda: types.SimpleNamespace(available_devices=["CPU"])),
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_entry.py",
            "detect",
            "--model",
            str(openvino_dir),
            "--source",
            "demo.mp4",
            "--output-dir",
            str(tmp_path / "out"),
            "--preview-path",
            str(tmp_path / "preview.jpg"),
            "--regions",
            str(regions),
            "--tracker",
            str(tracker),
            "--jam-signal-path",
            str(tmp_path / "jam.jsonl"),
            "--device",
            "intel:gpu",
        ],
    )
    assert worker.main() == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert "intel:gpu" in payload["message"].lower()

    broken_openvino_dir = tmp_path / "broken_openvino_model"
    broken_openvino_dir.mkdir()
    (broken_openvino_dir / "demo.xml").write_text("<xml />", encoding="utf-8")
    (broken_openvino_dir / "demo.bin").write_bytes(b"bin")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_entry.py",
            "detect",
            "--model",
            str(broken_openvino_dir),
            "--source",
            "demo.mp4",
            "--output-dir",
            str(tmp_path / "out2"),
            "--preview-path",
            str(tmp_path / "preview2.jpg"),
            "--regions",
            str(regions),
            "--tracker",
            str(tracker),
            "--jam-signal-path",
            str(tmp_path / "jam2.jsonl"),
            "--device",
            "intel:cpu",
        ],
    )
    assert worker.main() == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert "metadata.yaml" in payload["message"]


def test_openvino_device_validation_preserves_ultralytics_device_syntax(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = load_module(monkeypatch, "worker_entry_test_openvino_device_syntax", WORKER_ENTRY_PATH)
    monitor = load_module(monkeypatch, "monitor_test_openvino_device_syntax", PT_MONITOR_PATH)
    artifact = types.SimpleNamespace(backend="openvino")

    monkeypatch.setattr(worker, "available_openvino_devices", lambda: {"CPU", "GPU"})
    monkeypatch.setattr(monitor, "available_openvino_devices", lambda: {"CPU", "GPU"})

    assert worker.normalize_detect_device("auto", artifact) == "auto"
    assert worker.normalize_detect_device("intel:cpu", artifact) == "intel:cpu"
    assert worker.normalize_detect_device("intel:gpu", artifact) == "intel:gpu"
    assert monitor.validate_device("auto", artifact) == "cpu"
    assert monitor.validate_device("intel:cpu", artifact) == "intel:cpu"
    assert monitor.validate_device("intel:gpu", artifact) == "intel:gpu"


def test_openvino_device_discovery_uses_current_top_level_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_openvino = types.SimpleNamespace(
        Core=lambda: types.SimpleNamespace(available_devices=["CPU", "GPU"])
    )
    monkeypatch.setitem(sys.modules, "openvino", fake_openvino)
    monkeypatch.delitem(sys.modules, "openvino.runtime", raising=False)
    worker = load_module(monkeypatch, "worker_entry_test_openvino_api", WORKER_ENTRY_PATH)
    monitor = load_module(monkeypatch, "monitor_test_openvino_api", PT_MONITOR_PATH)

    assert worker.available_openvino_devices() == {"CPU", "GPU"}
    assert monitor.available_openvino_devices() == {"CPU", "GPU"}


def test_openvino_model_task_is_read_from_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monitor = load_module(monkeypatch, "monitor_test_openvino_task", PT_MONITOR_PATH)
    model_dir = write_openvino_model_bundle(tmp_path / "task_openvino_model")
    artifact = monitor.metadata_tools().resolve_model_artifact(model_dir)

    assert monitor.model_task_for_artifact(artifact) == "detect"


def test_onnx_model_task_is_read_from_metadata_and_autoinstall_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YOLO_AUTOINSTALL", "true")
    monitor = load_module(monkeypatch, "monitor_test_onnx_task", PT_MONITOR_PATH)
    model_path = tmp_path / "model.onnx"
    model_path.write_text("stub", encoding="utf-8")
    artifact = types.SimpleNamespace(
        backend="onnx",
        load_path=model_path,
        metadata_path=None,
    )
    monkeypatch.setattr(
        monitor,
        "metadata_tools",
        lambda: types.SimpleNamespace(inspect_onnx=lambda _path: {"task": "detect"}),
    )

    assert monitor.os.environ["YOLO_AUTOINSTALL"] == "false"
    assert monitor.model_task_for_artifact(artifact) == "detect"


def test_rtsp_capture_uses_ffmpeg_transport_and_timeouts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frames = [np.zeros((48, 48, 3), dtype=np.uint8) for _ in range(2)]
    fake_cv2 = FakeCv2(frames, fps=2.0, fail_read_after=1)
    module = load_module(
        monkeypatch,
        "pt_video_flow_monitor_test_rtsp_transport",
        PT_MONITOR_PATH,
        extra_modules={
            "cv2": fake_cv2,
            "ultralytics": types.SimpleNamespace(YOLO=lambda weights: FakeYOLO(weights, [[], []])),
        },
    )
    model = tmp_path / "model.pt"
    model.write_text("stub", encoding="utf-8")
    regions_path = write_regions(tmp_path / "regions.json")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pt_video_flow_monitor.py",
            "--model",
            str(model),
            "--source",
            "rtsp://camera/live",
            "--rtsp-transport",
            "udp",
            "--output-dir",
            str(tmp_path / "out"),
            "--preview-path",
            str(tmp_path / "preview.jpg"),
            "--regions",
            str(regions_path),
        ],
    )

    with pytest.raises(RuntimeError, match="视频流读取中断"):
        module.main()

    assert fake_cv2.video_capture_calls
    source, backend, params = fake_cv2.video_capture_calls[0]
    assert source == "rtsp://camera/live"
    assert backend == fake_cv2.CAP_FFMPEG
    assert fake_cv2.CAP_PROP_OPEN_TIMEOUT_MSEC in params
    assert fake_cv2.CAP_PROP_READ_TIMEOUT_MSEC in params


def test_probe_source_reports_json_without_password(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cv2 = FakeCv2([np.zeros((8, 8, 3), dtype=np.uint8)], fps=2.0, capture_opened=False)
    worker = load_module(
        monkeypatch,
        "worker_entry_test_probe_source",
        WORKER_ENTRY_PATH,
        extra_modules={"cv2": fake_cv2},
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_entry.py",
            "probe-source",
            "--source",
            "rtsp://user:secret@camera/live",
            "--rtsp-transport",
            "udp",
        ],
    )

    assert worker.main() == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["type"] == "probe"
    assert payload["ok"] is False
    assert payload["transport"] == "udp"
    assert "secret" not in json.dumps(payload, ensure_ascii=False)
