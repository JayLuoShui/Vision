# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
)

from dws_validator.config import RuntimeConfig, load_config
from dws_validator.diagnostics import diagnose_environment
from dws_validator.runtime_paths import RuntimePaths

from .widgets import PathSelector
from .worker import BatchValidationWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths = RuntimePaths()
        self.paths.ensure_user_dirs()
        self.thread: QThread | None = None
        self.worker: BatchValidationWorker | None = None
        self.started_at = 0.0

        self.setWindowTitle("DWS 批量模型检测验证工具")
        self.resize(1280, 820)
        self._build_ui()
        self._apply_style()
        self._load_defaults()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 10, 12, 12)
        left_layout.setSpacing(12)
        left.setMinimumWidth(500)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(520)
        left_scroll.setWidget(left)

        self.model_path = PathSelector("选择模型")
        self.images_dir = PathSelector("选择图片")
        self.labels_dir = PathSelector("选择标签")
        self.output_dir = PathSelector("选择输出")
        self.config_path = PathSelector("选择配置")
        self.openvino_dir_btn = QPushButton("OpenVINO目录")
        model_layout = self.model_path.layout()
        if model_layout is not None:
            model_layout.addWidget(self.openvino_dir_btn)
        self.model_path.button.clicked.connect(self.choose_model)
        self.openvino_dir_btn.clicked.connect(self.choose_openvino_dir)
        self.images_dir.button.clicked.connect(lambda: self.choose_dir(self.images_dir))
        self.labels_dir.button.clicked.connect(lambda: self.choose_dir(self.labels_dir))
        self.output_dir.button.clicked.connect(lambda: self.choose_dir(self.output_dir))
        self.config_path.button.clicked.connect(self.choose_config)

        paths_group = QGroupBox("路径设置")
        paths_form = QFormLayout(paths_group)
        paths_form.addRow("模型文件", self.model_path)
        paths_form.addRow("图片目录", self.images_dir)
        paths_form.addRow("标签目录", self.labels_dir)
        paths_form.addRow("输出目录", self.output_dir)
        paths_form.addRow("配置文件", self.config_path)

        params_group = QGroupBox("推理参数")
        params_form = QFormLayout(params_group)
        self.imgsz_h = QSpinBox()
        self.imgsz_h.setRange(64, 4096)
        self.imgsz_h.setValue(736)
        self.imgsz_w = QSpinBox()
        self.imgsz_w.setRange(64, 4096)
        self.imgsz_w.setValue(960)
        self.device = QComboBox()
        self.device.addItems(["自动", "CPU", "GPU"])
        self.low_conf = QDoubleSpinBox()
        self.low_conf.setRange(0.0, 1.0)
        self.low_conf.setSingleStep(0.01)
        self.low_conf.setValue(0.25)
        self.high_conf = QDoubleSpinBox()
        self.high_conf.setRange(0.0, 1.0)
        self.high_conf.setSingleStep(0.01)
        self.high_conf.setValue(0.55)
        self.iou = QDoubleSpinBox()
        self.iou.setRange(0.0, 1.0)
        self.iou.setSingleStep(0.01)
        self.iou.setValue(0.50)
        self.save_vis = QCheckBox("保存可视化图片")
        self.save_vis.setChecked(True)
        self.save_errors = QCheckBox("保存错误样本")
        self.save_errors.setChecked(True)
        self.vis_all = QCheckBox("保存全部 vis")
        self.vis_all.setChecked(True)
        params_form.addRow("输入尺寸 H", self.imgsz_h)
        params_form.addRow("输入尺寸 W", self.imgsz_w)
        params_form.addRow("执行设备", self.device)
        params_form.addRow("low_conf", self.low_conf)
        params_form.addRow("high_conf", self.high_conf)
        params_form.addRow("iou", self.iou)
        params_form.addRow("", self.save_vis)
        params_form.addRow("", self.save_errors)
        params_form.addRow("", self.vis_all)

        controls = QGroupBox("运行控制")
        controls_layout = QGridLayout(controls)
        self.start_btn = QPushButton("开始检测")
        self.cancel_btn = QPushButton("停止/取消")
        self.cancel_btn.setEnabled(False)
        self.diagnose_btn = QPushButton("环境自检")
        self.open_output_btn = QPushButton("打开输出目录")
        self.open_log_btn = QPushButton("打开日志目录")
        controls_layout.addWidget(self.start_btn, 0, 0)
        controls_layout.addWidget(self.cancel_btn, 0, 1)
        controls_layout.addWidget(self.diagnose_btn, 1, 0)
        controls_layout.addWidget(self.open_output_btn, 1, 1)
        controls_layout.addWidget(self.open_log_btn, 2, 0, 1, 2)
        self.start_btn.clicked.connect(self.start_batch)
        self.cancel_btn.clicked.connect(self.cancel_batch)
        self.diagnose_btn.clicked.connect(self.run_diagnose)
        self.open_output_btn.clicked.connect(lambda: self.open_dir(self.output_dir.text()))
        self.open_log_btn.clicked.connect(lambda: self.open_dir(str(self.paths.default_log_dir)))

        progress_group = QGroupBox("进度")
        progress_layout = QFormLayout(progress_group)
        self.progress = QProgressBar()
        self.current_image = QLabel("-")
        self.current_image.setWordWrap(True)
        self.current_status = QLabel("-")
        self.current_signal = QLabel("-")
        self.elapsed = QLabel("0 ms")
        progress_layout.addRow("进度", self.progress)
        progress_layout.addRow("当前图片", self.current_image)
        progress_layout.addRow("当前状态", self.current_status)
        progress_layout.addRow("当前信号", self.current_signal)
        progress_layout.addRow("当前耗时", self.elapsed)

        left_layout.addWidget(paths_group)
        left_layout.addWidget(params_group)
        left_layout.addWidget(controls)
        left_layout.addWidget(progress_group)
        left_layout.addStretch(1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.summary_labels: dict[str, QLabel] = {}
        summary_group = QGroupBox("结果摘要")
        summary_grid = QGridLayout(summary_group)
        keys = [
            "total_images",
            "labeled_images",
            "count_accuracy",
            "multi_gt_images",
            "multi_recall",
            "mean_ms",
            "p50_ms",
            "p95_ms",
            "max_ms",
            "SINGLE",
            "MULTI",
            "SUSPECT_MULTI",
            "UNKNOWN",
        ]
        for i, key in enumerate(keys):
            label = QLabel("-")
            self.summary_labels[key] = label
            summary_grid.addWidget(QLabel(key), i // 2, (i % 2) * 2)
            summary_grid.addWidget(label, i // 2, (i % 2) * 2 + 1)

        self.preview = QLabel("暂无预览")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(280)
        self.preview.setStyleSheet("border: 1px solid #3b4756; background: #111820;")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(220)

        right_layout.addWidget(summary_group)
        right_layout.addWidget(self.preview, 1)
        right_layout.addWidget(QLabel("日志"))
        right_layout.addWidget(self.log, 1)

        splitter.addWidget(left_scroll)
        splitter.addWidget(right)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([540, 820])
        root.addWidget(splitter)
        self.setCentralWidget(central)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_elapsed)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #18212b; color: #d8e0ea; font-size: 13px; }
            QScrollArea { border: none; background: #18212b; }
            QGroupBox { border: 1px solid #344252; border-radius: 4px; margin-top: 12px; padding: 10px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #8fb3ff; }
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #0f151c; color: #e6edf5; border: 1px solid #3b4756; border-radius: 3px; padding: 5px; }
            QPushButton { background: #25415f; border: 1px solid #45627f; border-radius: 3px; padding: 7px 10px; color: #f3f7fb; }
            QPushButton:hover { background: #315576; }
            QPushButton:disabled { background: #2a3037; color: #7b8794; }
            QProgressBar { border: 1px solid #3b4756; border-radius: 3px; text-align: center; background: #0f151c; }
            QProgressBar::chunk { background: #2f9e85; }
            QCheckBox { padding: 3px; }
            """
        )

    def _load_defaults(self) -> None:
        self.config_path.setText(str(self.paths.bundled_config_path))
        self.model_path.setText(str(self.paths.default_model_dir / "yolo26s-seg.pt"))
        self.images_dir.setText(str(self.paths.app_dir / "data" / "images"))
        self.labels_dir.setText(str(self.paths.app_dir / "data" / "labels"))
        self.output_dir.setText(str(self.paths.default_output_dir))

    def append_log(self, message: str) -> None:
        self.log.append(message)

    def choose_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择模型文件",
            self.model_path.text(),
            "模型文件 (*.pt *.xml);;PyTorch 模型 (*.pt);;OpenVINO XML (*.xml);;所有文件 (*.*)",
        )
        if path:
            self.model_path.setText(path)

    def choose_openvino_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择OpenVINO模型目录", self.model_path.text())
        if path:
            self.model_path.setText(path)

    def choose_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择配置文件", self.config_path.text(), "YAML (*.yaml *.yml);;所有文件 (*.*)")
        if path:
            self.config_path.setText(path)

    def choose_dir(self, selector: PathSelector) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择目录", selector.text())
        if path:
            selector.setText(path)

    def open_dir(self, path: str) -> None:
        target = Path(path)
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(str(target))  # type: ignore[attr-defined]

    def build_config(self) -> RuntimeConfig:
        device_map = {"自动": "auto", "CPU": "cpu", "GPU": "gpu"}
        cfg = load_config(
            self.config_path.text(),
            model=self.model_path.text(),
            images=self.images_dir.text(),
            labels=self.labels_dir.text(),
            output=self.output_dir.text(),
            imgsz=[self.imgsz_h.value(), self.imgsz_w.value()],
            device=device_map.get(self.device.currentText(), "auto"),
            low_conf=self.low_conf.value(),
            high_conf=self.high_conf.value(),
            iou=self.iou.value(),
        )
        cfg.save_vis = self.save_vis.isChecked()
        cfg.save_error_images = self.save_errors.isChecked()
        cfg.vis_all = self.vis_all.isChecked()
        return cfg

    def start_batch(self) -> None:
        try:
            cfg = self.build_config()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "参数错误", str(exc))
            return
        self.log.clear()
        self.progress.setValue(0)
        self.started_at = perf_counter()
        self.timer.start(100)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.thread = QThread(self)
        self.worker = BatchValidationWorker(cfg)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.on_progress)
        self.worker.rowReady.connect(self.on_row)
        self.worker.previewReady.connect(self.set_preview)
        self.worker.summaryReady.connect(self.set_summary)
        self.worker.failed.connect(self.on_failed)
        self.worker.cancelled.connect(lambda: self.append_log("任务已取消。"))
        self.worker.finished.connect(self.on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def cancel_batch(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.append_log("正在取消任务...")

    def on_progress(self, index: int, total: int, image_name: str) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(index)
        self.current_image.setText(f"{index}/{total} {image_name}")

    def on_row(self, row: dict) -> None:
        self.current_status.setText(str(row.get("status", "-")))
        self.current_signal.setText(str(row.get("signal", "-")))

    def set_preview(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def set_summary(self, summary: dict) -> None:
        for key, label in self.summary_labels.items():
            if key in {"SINGLE", "MULTI", "SUSPECT_MULTI", "UNKNOWN"}:
                value = summary.get("status_counts", {}).get(key, 0)
            else:
                value = summary.get(key, "-")
            label.setText(str(value))
        self.append_log(json.dumps(summary, ensure_ascii=False, indent=2))

    def on_failed(self, message: str) -> None:
        self.append_log(message)
        QMessageBox.critical(self, "检测失败", message)

    def on_finished(self) -> None:
        self.timer.stop()
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def update_elapsed(self) -> None:
        if self.started_at:
            elapsed_ms = (perf_counter() - self.started_at) * 1000.0
            self.elapsed.setText(f"{elapsed_ms:.0f} ms")

    def run_diagnose(self) -> None:
        result = diagnose_environment(self.model_path.text()).to_json()
        self.append_log(result)
        QMessageBox.information(self, "环境自检", result)
