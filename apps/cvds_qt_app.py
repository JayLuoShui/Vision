from __future__ import annotations

import csv
import json
import os
import socket
import subprocess
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QPointF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from scripts.training_monitor import find_latest_training_run, read_results, read_training_snapshot


def find_project_root() -> Path:
    if os.environ.get("CVDS_ROOT"):
        return Path(os.environ["CVDS_ROOT"]).resolve()
    start = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    for candidate in [start, *start.parents]:
        if (
            (candidate / "datasets" / "cvds_package_yolo26_crossbelt_v2" / "data.yaml").exists()
            or (candidate / "datasets" / "cvds_package_yolo26_crossbelt" / "data.yaml").exists()
            or (candidate / "datasets" / "cvds_package_yolo26" / "data.yaml").exists()
            or (candidate / "weights").exists()
        ):
            return candidate
    return start


ROOT = find_project_root()
DEFAULT_DATA_BASE = ROOT / "datasets" / "cvds_package_yolo26" / "data.yaml"
DEFAULT_DATA_CROSSBELT = ROOT / "datasets" / "cvds_package_yolo26_crossbelt" / "data.yaml"
DEFAULT_DATA = DEFAULT_DATA_CROSSBELT if DEFAULT_DATA_CROSSBELT.exists() else DEFAULT_DATA_BASE
DEFAULT_BASE_MODEL = ROOT / "weights" / "pretrained" / "yolo26n.pt"
DEFAULT_WEIGHTS = ROOT / "weights" / "cvds_yolo26n_package_best.pt"
DEFAULT_RUNS = ROOT / "runs" / "gui_train"
DEFAULT_PACKAGE_TRAIN = ROOT / "runs" / "package_train"
DEFAULT_EVENTS = ROOT / "runs" / "plc_events" / "package_events.jsonl"
DEFAULT_VIDEO_MKV = ROOT / "Loop Cross-Belt Sorter in real operation [VSHu55q3tE8].mkv"
DEFAULT_VIDEO_MP4 = ROOT / "Loop Cross-Belt Sorter in real operation [VSHu55q3tE8].mp4"
DEFAULT_VIDEO = DEFAULT_VIDEO_MKV if DEFAULT_VIDEO_MKV.exists() else DEFAULT_VIDEO_MP4
CUDA_NAME_CACHE: str | None = None
CUDA_CHECKED = False


def detect_cuda_name() -> str | None:
    global CUDA_CHECKED, CUDA_NAME_CACHE
    if CUDA_CHECKED:
        return CUDA_NAME_CACHE
    command = ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    if result.returncode != 0:
        CUDA_CHECKED = True
        CUDA_NAME_CACHE = None
        return None
    first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    CUDA_CHECKED = True
    CUDA_NAME_CACHE = first_line or None
    return CUDA_NAME_CACHE


def default_device_options() -> list[str]:
    return ["0", "cpu"] if detect_cuda_name() else ["cpu"]


def torch_cuda_available() -> bool:
    import torch

    return torch.cuda.is_available()


def parse_roi_text(text: str) -> list[tuple[int, int]] | None:
    text = text.strip()
    if not text:
        return None
    values = [int(float(x.strip())) for x in text.split(",") if x.strip()]
    if len(values) < 4 or len(values) % 2 != 0:
        raise ValueError("检测ROI必须是 x1,y1,x2,y2 或多边形点列表")
    return [(values[i], values[i + 1]) for i in range(0, len(values), 2)]


def crop_by_roi(frame: Any, polygon: list[tuple[int, int]] | None) -> tuple[Any, tuple[int, int], tuple[int, int, int, int] | None]:
    import cv2
    import numpy as np

    if not polygon:
        return frame, (0, 0), None
    height, width = frame.shape[:2]
    contour = np.array(polygon, dtype=np.int32)
    x, y, w, h = cv2.boundingRect(contour)
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(width, x + w)
    y2 = min(height, y + h)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("检测ROI超出画面或面积为0")
    return frame[y1:y2, x1:x2], (x1, y1), (x1, y1, x2, y2)


class StreamEmitter:
    def __init__(self, callback):
        self.callback = callback
        self._buffer = ""

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self.callback(line.rstrip())
        return len(text)

    def flush(self) -> None:
        if self._buffer.strip():
            self.callback(self._buffer.rstrip())
        self._buffer = ""


class MetricsPlot(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(180)
        self.metrics: list[dict[str, float]] = []

    def set_metrics(self, rows: list[dict[str, float]]) -> None:
        self.metrics = rows
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111827"))
        rect = self.rect().adjusted(48, 18, -18, -34)
        painter.setPen(QPen(QColor("#4b5563"), 1))
        painter.drawRect(rect)
        painter.setPen(QColor("#d1d5db"))
        painter.drawText(12, 18, "mAP")
        painter.drawText(rect.left(), self.height() - 10, "epoch")

        if len(self.metrics) < 1:
            painter.drawText(rect, Qt.AlignCenter, "等待训练指标")
            return

        epochs = [row["epoch"] for row in self.metrics]
        series = [
            ("mAP50", "metrics/mAP50(B)", QColor("#22c55e")),
            ("mAP50-95", "metrics/mAP50-95(B)", QColor("#38bdf8")),
            ("Recall", "metrics/recall(B)", QColor("#f59e0b")),
        ]
        min_epoch, max_epoch = min(epochs), max(epochs)
        if min_epoch == max_epoch:
            max_epoch += 1

        for i in range(6):
            y = rect.bottom() - i * rect.height() / 5
            painter.setPen(QPen(QColor("#374151"), 1))
            painter.drawLine(rect.left(), y, rect.right(), y)
            painter.setPen(QColor("#9ca3af"))
            painter.drawText(8, int(y + 4), f"{i/5:.1f}")

        for name, key, color in series:
            points = []
            for row in self.metrics:
                value = max(0.0, min(1.0, row.get(key, 0.0)))
                x = rect.left() + (row["epoch"] - min_epoch) / (max_epoch - min_epoch) * rect.width()
                y = rect.bottom() - value * rect.height()
                points.append(QPointF(x, y))
            painter.setPen(QPen(color, 2))
            for a, b in zip(points, points[1:]):
                painter.drawLine(a, b)
            painter.drawText(rect.right() - 130, rect.top() + 18 + series.index((name, key, color)) * 18, name)


class TrainWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__()
        self.params = params

    def run(self) -> None:
        try:
            from ultralytics import YOLO

            model = YOLO(self.params["model"])
            train_args = {
                "data": self.params["data"],
                "epochs": self.params["epochs"],
                "imgsz": self.params["imgsz"],
                "batch": self.params["batch"],
                "workers": self.params["workers"],
                "device": self.params["device"],
                "project": self.params["project"],
                "name": self.params["name"],
                "exist_ok": True,
                "pretrained": True,
                "optimizer": "AdamW",
                "lr0": 0.002,
                "lrf": 0.01,
                "weight_decay": 0.0005,
                "warmup_epochs": 3.0,
                "cos_lr": True,
                "close_mosaic": 10,
                "mosaic": 1.0,
                "mixup": 0.0,
                "copy_paste": 0.0,
                "hsv_h": 0.01,
                "hsv_s": 0.35,
                "hsv_v": 0.25,
                "degrees": 2.0,
                "translate": 0.08,
                "scale": 0.70,
                "shear": 0.0,
                "perspective": 0.0,
                "fliplr": 0.5,
                "flipud": 0.0,
                "cache": False,
                "multi_scale": 0.35 if torch_cuda_available() else 0.0,
                "plots": True,
                "val": True,
                "save": True,
                "seed": 20260506,
                "deterministic": True,
            }
            self.log.emit("训练参数：" + json.dumps(train_args, ensure_ascii=False))
            stream = StreamEmitter(self.log.emit)
            with redirect_stdout(stream), redirect_stderr(stream):
                result = model.train(**train_args)
            stream.flush()
            save_dir = Path(result.save_dir)
            summary = {
                "save_dir": str(save_dir),
                "best": str(save_dir / "weights" / "best.pt"),
                "last": str(save_dir / "weights" / "last.pt"),
            }
            (save_dir / "cvds_gui_train_summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.done.emit(summary)
        except Exception:
            self.failed.emit(traceback.format_exc())


@dataclass
class PlcConfig:
    jsonl_enabled: bool
    jsonl_path: Path
    tcp_enabled: bool
    tcp_host: str
    tcp_port: int
    http_enabled: bool
    http_url: str


class PlcEventSink:
    def __init__(self, config: PlcConfig):
        self.config = config

    def emit(self, event: dict[str, Any]) -> list[str]:
        messages = []
        payload = json.dumps(event, ensure_ascii=False)
        if self.config.jsonl_enabled:
            self.config.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config.jsonl_path.open("a", encoding="utf-8") as f:
                f.write(payload + "\n")
            messages.append("JSONL")
        if self.config.tcp_enabled:
            with socket.create_connection((self.config.tcp_host, self.config.tcp_port), timeout=1.5) as sock:
                sock.sendall((payload + "\n").encode("utf-8"))
            messages.append("TCP")
        if self.config.http_enabled:
            import requests

            requests.post(self.config.http_url, json=event, timeout=2.0)
            messages.append("HTTP")
        return messages


class DetectWorker(QObject):
    frame = Signal(QImage)
    log = Signal(str)
    event = Signal(dict)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, params: dict[str, Any], plc_config: PlcConfig) -> None:
        super().__init__()
        self.params = params
        self.plc_config = plc_config
        self._stop = False
        self._last_event_ts = 0.0

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            from ultralytics import YOLO

            model = YOLO(self.params["weights"])
            source = self.params["source"]
            sink = PlcEventSink(self.plc_config)
            if self.params["mode"] == "image":
                self._run_image(model, source, sink)
            else:
                self._run_video(model, source, sink)
        except Exception:
            self.failed.emit(traceback.format_exc())

    def _run_image(self, model: Any, source: str, sink: PlcEventSink) -> None:
        import cv2
        import numpy as np

        image = cv2.imdecode(np.fromfile(source, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("图片读取失败")
        detect_roi = parse_roi_text(self.params.get("detect_roi", ""))
        annotated, boxes = self._predict_and_draw(model, image, source, 1, detect_roi)
        self.frame.emit(cv_to_qimage(annotated))
        if boxes:
            self._emit_package_event(sink, source, 1, boxes)
        self.done.emit({"frames": 1, "events": 1 if boxes else 0})

    def _run_video(self, model: Any, source: str, sink: PlcEventSink) -> None:
        import cv2

        cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)
        if not cap.isOpened():
            raise RuntimeError("视频源打开失败")
        frame_idx = 0
        event_count = 0
        detect_roi = parse_roi_text(self.params.get("detect_roi", ""))
        while not self._stop:
            ok, frame = cap.read()
            if not ok:
                break
            frame_idx += 1
            annotated, boxes = self._predict_and_draw(model, frame, source, frame_idx, detect_roi)
            self.frame.emit(cv_to_qimage(annotated))
            if boxes and time.time() - self._last_event_ts >= self.params["cooldown"]:
                self._emit_package_event(sink, source, frame_idx, boxes)
                self._last_event_ts = time.time()
                event_count += 1
            QThread.msleep(max(1, int(1000 / max(1, self.params["display_fps"]))))
        cap.release()
        self.done.emit({"frames": frame_idx, "events": event_count})

    def _predict_and_draw(
        self,
        model: Any,
        frame: Any,
        source: str,
        frame_idx: int,
        detect_roi: list[tuple[int, int]] | None,
    ) -> tuple[Any, list[dict]]:
        import cv2

        infer_frame, offset, detect_roi_rect = crop_by_roi(frame, detect_roi)
        result = model.predict(
            infer_frame,
            conf=self.params["conf"],
            imgsz=self.params["imgsz"],
            device=self.params["device"],
            verbose=False,
        )[0]
        boxes = []
        annotated = frame.copy()
        if result.boxes is not None:
            for box, conf, cls in zip(result.boxes.xyxy.cpu().numpy(), result.boxes.conf.cpu().numpy(), result.boxes.cls.cpu().numpy()):
                if int(cls) != 0:
                    continue
                x1, y1, x2, y2 = [int(v) for v in box]
                x1 += offset[0]
                x2 += offset[0]
                y1 += offset[1]
                y2 += offset[1]
                boxes.append(
                    {
                        "class_id": 0,
                        "class_name": "parcel",
                        "confidence": float(conf),
                        "xyxy": [x1, y1, x2, y2],
                    }
                )
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 220, 0), 2)
                cv2.putText(
                    annotated,
                    f"parcel {conf:.2f}",
                    (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 220, 0),
                    2,
                )
        if detect_roi_rect:
            x1, y1, x2, y2 = detect_roi_rect
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 160, 0), 2)
        cv2.putText(annotated, f"frame {frame_idx} parcels {len(boxes)}", (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(annotated, f"frame {frame_idx} parcels {len(boxes)}", (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        return annotated, boxes

    def _emit_package_event(self, sink: PlcEventSink, source: str, frame_idx: int, boxes: list[dict]) -> None:
        event = {
            "event_type": "package_detected",
            "timestamp_ms": int(time.time() * 1000),
            "source": source,
            "frame_index": frame_idx,
            "package_count": len(boxes),
            "boxes": boxes,
        }
        try:
            channels = sink.emit(event)
            self.log.emit("PLC事件输出：" + ",".join(channels) + " " + json.dumps(event, ensure_ascii=False))
        except Exception as exc:
            self.log.emit("PLC事件输出失败：" + str(exc))
        self.event.emit(event)


def cv_to_qimage(frame: Any) -> QImage:
    import cv2

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CVDS 包裹检测训练与联动平台")
        self.resize(1280, 820)
        self.train_thread: QThread | None = None
        self.train_worker: TrainWorker | None = None
        self.detect_thread: QThread | None = None
        self.detect_worker: DetectWorker | None = None
        self.metrics_timer = QTimer(self)
        self.metrics_timer.timeout.connect(self.refresh_metrics)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.refresh_training_monitor)
        self.current_results_csv: Path | None = None
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.build_train_tab()
        self.build_training_monitor_tab()
        self.build_detect_tab()
        self.build_plc_tab()
        self.monitor_timer.start(5000)
        self.refresh_training_monitor()
        self.statusBar().showMessage(self.device_text())

    def device_text(self) -> str:
        cuda_name = detect_cuda_name()
        if cuda_name:
            return f"CUDA 可用：{cuda_name}"
        return "CUDA 不可用：默认使用 CPU"

    def build_train_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        form_box = QGroupBox("训练参数")
        form = QGridLayout(form_box)
        self.data_edit = QLineEdit(str(DEFAULT_DATA))
        self.model_edit = QLineEdit(str(DEFAULT_BASE_MODEL))
        self.project_edit = QLineEdit(str(DEFAULT_RUNS))
        self.name_edit = QLineEdit("qt_yolo26n_package")
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1, 300)
        self.epochs_spin.setValue(12)
        self.imgsz_spin = QSpinBox()
        self.imgsz_spin.setRange(160, 1536)
        self.imgsz_spin.setValue(960)
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 128)
        self.batch_spin.setValue(4 if detect_cuda_name() else 8)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(0, 16)
        self.workers_spin.setValue(4)
        self.device_combo = QComboBox()
        self.device_combo.addItems(default_device_options())
        add_path_row(form, 0, "数据配置", self.data_edit, self.pick_data)
        add_path_row(form, 1, "基础模型", self.model_edit, self.pick_model)
        add_path_row(form, 2, "输出目录", self.project_edit, self.pick_project)
        form.addWidget(QLabel("实验名称"), 3, 0)
        form.addWidget(self.name_edit, 3, 1)
        form.addWidget(QLabel("轮数"), 4, 0)
        form.addWidget(self.epochs_spin, 4, 1)
        form.addWidget(QLabel("输入尺寸"), 5, 0)
        form.addWidget(self.imgsz_spin, 5, 1)
        form.addWidget(QLabel("Batch"), 6, 0)
        form.addWidget(self.batch_spin, 6, 1)
        form.addWidget(QLabel("Workers"), 7, 0)
        form.addWidget(self.workers_spin, 7, 1)
        form.addWidget(QLabel("设备"), 8, 0)
        form.addWidget(self.device_combo, 8, 1)

        self.start_train_btn = QPushButton("开始训练")
        self.start_train_btn.clicked.connect(self.start_training)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.start_train_btn)
        btn_row.addWidget(self.progress)

        self.metrics_plot = MetricsPlot()
        self.metrics_table = QTableWidget(0, 5)
        self.metrics_table.setHorizontalHeaderLabels(["epoch", "precision", "recall", "mAP50", "mAP50-95"])
        self.train_log = QPlainTextEdit()
        self.train_log.setReadOnly(True)
        split = QSplitter(Qt.Vertical)
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.addWidget(self.metrics_plot)
        top_layout.addWidget(self.metrics_table)
        split.addWidget(top)
        split.addWidget(self.train_log)
        split.setSizes([360, 300])
        layout.addWidget(form_box)
        layout.addLayout(btn_row)
        layout.addWidget(split)
        self.tabs.addTab(page, "模型训练")

    def build_training_monitor_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        run_box = QGroupBox("监控目录")
        run_layout = QGridLayout(run_box)
        latest = find_latest_training_run(DEFAULT_PACKAGE_TRAIN)
        self.monitor_run_edit = QLineEdit(str(latest or DEFAULT_PACKAGE_TRAIN))
        add_path_row(run_layout, 0, "训练目录", self.monitor_run_edit, self.pick_monitor_run)
        self.monitor_auto_check = QCheckBox("自动刷新")
        self.monitor_auto_check.setChecked(True)
        self.monitor_auto_check.toggled.connect(self.toggle_monitor_timer)
        latest_btn = QPushButton("最新训练")
        latest_btn.clicked.connect(self.use_latest_training_run)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_training_monitor)
        run_layout.addWidget(self.monitor_auto_check, 1, 0)
        run_layout.addWidget(latest_btn, 1, 1)
        run_layout.addWidget(refresh_btn, 1, 2)

        status_box = QGroupBox("训练进度")
        status_layout = QGridLayout(status_box)
        self.monitor_status_label = QLabel("等待读取")
        self.monitor_epoch_label = QLabel("-")
        self.monitor_latest_label = QLabel("-")
        self.monitor_best_label = QLabel("-")
        self.monitor_weight_label = QLabel("-")
        self.monitor_progress = QProgressBar()
        self.monitor_progress.setRange(0, 100)
        status_layout.addWidget(QLabel("进程"), 0, 0)
        status_layout.addWidget(self.monitor_status_label, 0, 1)
        status_layout.addWidget(QLabel("轮数"), 1, 0)
        status_layout.addWidget(self.monitor_epoch_label, 1, 1)
        status_layout.addWidget(QLabel("进度"), 2, 0)
        status_layout.addWidget(self.monitor_progress, 2, 1)
        status_layout.addWidget(QLabel("最新指标"), 3, 0)
        status_layout.addWidget(self.monitor_latest_label, 3, 1)
        status_layout.addWidget(QLabel("最好指标"), 4, 0)
        status_layout.addWidget(self.monitor_best_label, 4, 1)
        status_layout.addWidget(QLabel("权重文件"), 5, 0)
        status_layout.addWidget(self.monitor_weight_label, 5, 1)

        self.monitor_metrics_plot = MetricsPlot()
        self.monitor_metrics_table = QTableWidget(0, 5)
        self.monitor_metrics_table.setHorizontalHeaderLabels(["epoch", "precision", "recall", "mAP50", "mAP50-95"])
        self.monitor_args_table = QTableWidget(0, 2)
        self.monitor_args_table.setHorizontalHeaderLabels(["参数", "值"])
        split = QSplitter(Qt.Vertical)
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.addWidget(self.monitor_metrics_plot)
        top_layout.addWidget(self.monitor_metrics_table)
        split.addWidget(top)
        split.addWidget(self.monitor_args_table)
        split.setSizes([420, 240])

        layout.addWidget(run_box)
        layout.addWidget(status_box)
        layout.addWidget(split)
        self.tabs.addTab(page, "训练监控")

    def build_detect_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        cfg = QGroupBox("检测配置")
        form = QGridLayout(cfg)
        self.weights_edit = QLineEdit(str(DEFAULT_WEIGHTS))
        self.source_edit = QLineEdit(str(DEFAULT_VIDEO if DEFAULT_VIDEO.exists() else ""))
        self.detect_mode_combo = QComboBox()
        self.detect_mode_combo.addItems(["video", "image"])
        self.conf_edit = QLineEdit("0.35")
        self.detect_imgsz_spin = QSpinBox()
        self.detect_imgsz_spin.setRange(160, 1536)
        self.detect_imgsz_spin.setValue(960)
        self.detect_device_combo = QComboBox()
        self.detect_device_combo.addItems(default_device_options())
        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(0, 60)
        self.cooldown_spin.setValue(2)
        self.display_fps_spin = QSpinBox()
        self.display_fps_spin.setRange(1, 60)
        self.display_fps_spin.setValue(15)
        self.detect_roi_edit = QLineEdit("")
        add_path_row(form, 0, "模型权重", self.weights_edit, self.pick_weights)
        add_path_row(form, 1, "输入源", self.source_edit, self.pick_source)
        form.addWidget(QLabel("类型"), 2, 0)
        form.addWidget(self.detect_mode_combo, 2, 1)
        form.addWidget(QLabel("置信度"), 3, 0)
        form.addWidget(self.conf_edit, 3, 1)
        form.addWidget(QLabel("输入尺寸"), 4, 0)
        form.addWidget(self.detect_imgsz_spin, 4, 1)
        form.addWidget(QLabel("设备"), 5, 0)
        form.addWidget(self.detect_device_combo, 5, 1)
        form.addWidget(QLabel("事件冷却秒"), 6, 0)
        form.addWidget(self.cooldown_spin, 6, 1)
        form.addWidget(QLabel("显示FPS"), 7, 0)
        form.addWidget(self.display_fps_spin, 7, 1)
        form.addWidget(QLabel("检测ROI"), 8, 0)
        form.addWidget(self.detect_roi_edit, 8, 1)

        self.start_detect_btn = QPushButton("开始检测")
        self.start_detect_btn.clicked.connect(self.start_detection)
        self.stop_detect_btn = QPushButton("停止检测")
        self.stop_detect_btn.clicked.connect(self.stop_detection)
        self.stop_detect_btn.setEnabled(False)
        row = QHBoxLayout()
        row.addWidget(self.start_detect_btn)
        row.addWidget(self.stop_detect_btn)
        self.video_label = QLabel("等待输入")
        self.video_label.setMinimumSize(820, 460)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background:#111827;color:#d1d5db;")
        self.detect_log = QPlainTextEdit()
        self.detect_log.setReadOnly(True)
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.video_label)
        split.addWidget(self.detect_log)
        split.setSizes([900, 360])
        layout.addWidget(cfg)
        layout.addLayout(row)
        layout.addWidget(split)
        self.tabs.addTab(page, "检测展示")

    def build_plc_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("PLC 联动预留输出")
        form = QFormLayout(box)
        self.jsonl_check = QCheckBox("启用 JSONL 文件输出")
        self.jsonl_check.setChecked(True)
        self.jsonl_edit = QLineEdit(str(DEFAULT_EVENTS))
        self.tcp_check = QCheckBox("启用 TCP JSON 输出")
        self.tcp_host_edit = QLineEdit("127.0.0.1")
        self.tcp_port_spin = QSpinBox()
        self.tcp_port_spin.setRange(1, 65535)
        self.tcp_port_spin.setValue(15000)
        self.http_check = QCheckBox("启用 HTTP POST 输出")
        self.http_url_edit = QLineEdit("http://127.0.0.1:18080/cvds/event")
        form.addRow(self.jsonl_check)
        file_row = QHBoxLayout()
        file_row.addWidget(self.jsonl_edit)
        pick = QPushButton("选择")
        pick.clicked.connect(self.pick_jsonl)
        file_row.addWidget(pick)
        form.addRow("JSONL路径", file_row)
        form.addRow(self.tcp_check)
        form.addRow("TCP主机", self.tcp_host_edit)
        form.addRow("TCP端口", self.tcp_port_spin)
        form.addRow(self.http_check)
        form.addRow("HTTP URL", self.http_url_edit)
        self.event_table = QTableWidget(0, 4)
        self.event_table.setHorizontalHeaderLabels(["时间", "来源", "帧", "包裹数"])
        layout.addWidget(box)
        layout.addWidget(QLabel("检测到包裹后会输出 JSON 事件，默认只写本地文件。TCP/HTTP 由现场 PLC 网关或上位机接入。"))
        layout.addWidget(self.event_table)
        self.tabs.addTab(page, "PLC接口")

    def pick_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 data.yaml", str(ROOT), "YAML (*.yaml *.yml)")
        if path:
            self.data_edit.setText(path)

    def pick_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择基础模型", str(ROOT), "PyTorch (*.pt)")
        if path:
            self.model_edit.setText(path)

    def pick_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", str(ROOT / "runs"))
        if path:
            self.project_edit.setText(path)

    def pick_monitor_run(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择训练目录", str(DEFAULT_PACKAGE_TRAIN))
        if path:
            self.monitor_run_edit.setText(path)
            self.refresh_training_monitor()

    def pick_weights(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择权重", str(ROOT / "weights"), "PyTorch (*.pt)")
        if path:
            self.weights_edit.setText(path)

    def pick_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择图片或视频", str(ROOT), "Media (*.jpg *.jpeg *.png *.bmp *.mp4 *.avi *.mkv *.mov)")
        if path:
            self.source_edit.setText(path)

    def pick_jsonl(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "选择事件输出文件", str(DEFAULT_EVENTS), "JSONL (*.jsonl)")
        if path:
            self.jsonl_edit.setText(path)

    def plc_config(self) -> PlcConfig:
        return PlcConfig(
            jsonl_enabled=self.jsonl_check.isChecked(),
            jsonl_path=Path(self.jsonl_edit.text()),
            tcp_enabled=self.tcp_check.isChecked(),
            tcp_host=self.tcp_host_edit.text().strip(),
            tcp_port=self.tcp_port_spin.value(),
            http_enabled=self.http_check.isChecked(),
            http_url=self.http_url_edit.text().strip(),
        )

    def start_training(self) -> None:
        if self.train_thread is not None:
            return
        params = {
            "data": self.data_edit.text(),
            "model": self.model_edit.text(),
            "project": self.project_edit.text(),
            "name": self.name_edit.text().strip() or "qt_yolo26n_package",
            "epochs": self.epochs_spin.value(),
            "imgsz": self.imgsz_spin.value(),
            "batch": self.batch_spin.value(),
            "workers": self.workers_spin.value(),
            "device": self.device_combo.currentText(),
        }
        self.current_results_csv = Path(params["project"]) / params["name"] / "results.csv"
        self.monitor_run_edit.setText(str(Path(params["project"]) / params["name"]))
        self.train_log.clear()
        self.metrics_table.setRowCount(0)
        self.metrics_plot.set_metrics([])
        self.start_train_btn.setEnabled(False)
        self.progress.show()
        self.train_thread = QThread()
        self.train_worker = TrainWorker(params)
        self.train_worker.moveToThread(self.train_thread)
        self.train_thread.started.connect(self.train_worker.run)
        self.train_worker.log.connect(self.append_train_log)
        self.train_worker.done.connect(self.train_done)
        self.train_worker.failed.connect(self.train_failed)
        self.train_worker.done.connect(self.train_thread.quit)
        self.train_worker.failed.connect(self.train_thread.quit)
        self.train_thread.finished.connect(self.cleanup_train_thread)
        self.train_thread.start()
        self.metrics_timer.start(3000)

    def append_train_log(self, text: str) -> None:
        self.train_log.appendPlainText(text)

    def train_done(self, summary: dict) -> None:
        self.append_train_log("训练完成：" + json.dumps(summary, ensure_ascii=False))
        self.refresh_metrics()

    def train_failed(self, error: str) -> None:
        self.append_train_log(error)
        QMessageBox.critical(self, "训练失败", error[:2000])

    def cleanup_train_thread(self) -> None:
        self.metrics_timer.stop()
        self.progress.hide()
        self.start_train_btn.setEnabled(True)
        self.train_thread = None
        self.train_worker = None

    def toggle_monitor_timer(self, enabled: bool) -> None:
        if enabled:
            self.monitor_timer.start(5000)
            self.refresh_training_monitor()
        else:
            self.monitor_timer.stop()

    def use_latest_training_run(self) -> None:
        latest = find_latest_training_run(DEFAULT_PACKAGE_TRAIN)
        if latest is None:
            QMessageBox.warning(self, "没有训练记录", f"没有找到训练目录：{DEFAULT_PACKAGE_TRAIN}")
            return
        self.monitor_run_edit.setText(str(latest))
        self.refresh_training_monitor()

    def refresh_training_monitor(self) -> None:
        run_dir = Path(self.monitor_run_edit.text().strip())
        if run_dir == DEFAULT_PACKAGE_TRAIN:
            latest = find_latest_training_run(DEFAULT_PACKAGE_TRAIN)
            if latest is None:
                self.monitor_status_label.setText("没有找到训练记录")
                return
            run_dir = latest
            self.monitor_run_edit.setText(str(run_dir))
        snapshot = read_training_snapshot(run_dir)
        status = "运行中" if snapshot.process.running else "未发现训练进程"
        if snapshot.process.process_id is not None:
            status += f"  PID {snapshot.process.process_id}"
        self.monitor_status_label.setText(status)
        self.monitor_epoch_label.setText(f"{snapshot.finished_epochs}/{snapshot.total_epochs}")
        self.monitor_progress.setValue(min(100, int(round(snapshot.progress_percent))))

        latest = snapshot.latest_metrics
        self.monitor_latest_label.setText(
            "precision={:.3f}  recall={:.3f}  mAP50={:.3f}  mAP50-95={:.3f}".format(
                latest.get("metrics/precision(B)", 0.0),
                latest.get("metrics/recall(B)", 0.0),
                latest.get("metrics/mAP50(B)", 0.0),
                latest.get("metrics/mAP50-95(B)", 0.0),
            )
        )
        self.monitor_best_label.setText(
            "mAP50={:.3f}  mAP50-95={:.3f}".format(snapshot.best_map50, snapshot.best_map5095)
        )
        weight_texts = []
        for name, item in snapshot.weights.items():
            if item.exists and item.modified_at is not None:
                size_mb = item.size_bytes / (1024 * 1024)
                weight_texts.append(f"{name}: {size_mb:.1f}MB, {item.modified_at:%H:%M:%S}")
            else:
                weight_texts.append(f"{name}: 未生成")
        self.monitor_weight_label.setText(" | ".join(weight_texts))

        rows = read_results(run_dir / "results.csv")
        self.monitor_metrics_plot.set_metrics(rows)
        self.fill_metrics_table(self.monitor_metrics_table, rows)
        self.fill_args_table(snapshot.args)

    def refresh_metrics(self) -> None:
        if not self.current_results_csv or not self.current_results_csv.exists():
            return
        rows = []
        with self.current_results_csv.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    rows.append({k.strip(): float(v) for k, v in row.items() if v != ""})
                except ValueError:
                    continue
        self.metrics_plot.set_metrics(rows)
        self.fill_metrics_table(self.metrics_table, rows)

    def fill_metrics_table(self, table: QTableWidget, rows: list[dict[str, float]]) -> None:
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row.get("epoch", 0),
                row.get("metrics/precision(B)", 0),
                row.get("metrics/recall(B)", 0),
                row.get("metrics/mAP50(B)", 0),
                row.get("metrics/mAP50-95(B)", 0),
            ]
            for c, value in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(f"{value:.4f}"))

    def fill_args_table(self, args: dict[str, str]) -> None:
        ordered_keys = [
            "model",
            "data",
            "epochs",
            "imgsz",
            "batch",
            "device",
            "optimizer",
            "lr0",
            "lrf",
            "patience",
            "project",
            "name",
        ]
        keys = [key for key in ordered_keys if key in args]
        keys.extend(sorted(key for key in args if key not in set(keys)))
        self.monitor_args_table.setRowCount(len(keys))
        for row, key in enumerate(keys):
            self.monitor_args_table.setItem(row, 0, QTableWidgetItem(key))
            self.monitor_args_table.setItem(row, 1, QTableWidgetItem(args[key]))

    def start_detection(self) -> None:
        if self.detect_thread is not None:
            return
        params = {
            "weights": self.weights_edit.text(),
            "source": self.source_edit.text(),
            "mode": self.detect_mode_combo.currentText(),
            "conf": float(self.conf_edit.text()),
            "imgsz": self.detect_imgsz_spin.value(),
            "device": self.detect_device_combo.currentText(),
            "cooldown": self.cooldown_spin.value(),
            "display_fps": self.display_fps_spin.value(),
            "detect_roi": self.detect_roi_edit.text().strip(),
        }
        self.detect_log.clear()
        self.start_detect_btn.setEnabled(False)
        self.stop_detect_btn.setEnabled(True)
        self.detect_thread = QThread()
        self.detect_worker = DetectWorker(params, self.plc_config())
        self.detect_worker.moveToThread(self.detect_thread)
        self.detect_thread.started.connect(self.detect_worker.run)
        self.detect_worker.frame.connect(self.show_frame)
        self.detect_worker.log.connect(self.append_detect_log)
        self.detect_worker.event.connect(self.add_event_row)
        self.detect_worker.done.connect(self.detect_done)
        self.detect_worker.failed.connect(self.detect_failed)
        self.detect_worker.done.connect(self.detect_thread.quit)
        self.detect_worker.failed.connect(self.detect_thread.quit)
        self.detect_thread.finished.connect(self.cleanup_detect_thread)
        self.detect_thread.start()

    def stop_detection(self) -> None:
        if self.detect_worker is not None:
            self.detect_worker.stop()

    def show_frame(self, image: QImage) -> None:
        pix = QPixmap.fromImage(image)
        self.video_label.setPixmap(pix.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def append_detect_log(self, text: str) -> None:
        self.detect_log.appendPlainText(text)

    def detect_done(self, summary: dict) -> None:
        self.append_detect_log("检测完成：" + json.dumps(summary, ensure_ascii=False))

    def detect_failed(self, error: str) -> None:
        self.append_detect_log(error)
        QMessageBox.critical(self, "检测失败", error[:2000])

    def cleanup_detect_thread(self) -> None:
        self.start_detect_btn.setEnabled(True)
        self.stop_detect_btn.setEnabled(False)
        self.detect_thread = None
        self.detect_worker = None

    def add_event_row(self, event: dict) -> None:
        row = self.event_table.rowCount()
        self.event_table.insertRow(row)
        values = [
            str(event.get("timestamp_ms", "")),
            str(event.get("source", "")),
            str(event.get("frame_index", "")),
            str(event.get("package_count", "")),
        ]
        for col, value in enumerate(values):
            self.event_table.setItem(row, col, QTableWidgetItem(value))


def add_path_row(layout: QGridLayout, row: int, label: str, edit: QLineEdit, callback) -> None:
    button = QPushButton("选择")
    button.clicked.connect(callback)
    layout.addWidget(QLabel(label), row, 0)
    layout.addWidget(edit, row, 1)
    layout.addWidget(button, row, 2)


def main() -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
