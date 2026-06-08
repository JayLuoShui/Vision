from __future__ import annotations

import logging
import os
import json
import sys
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .core import (
    apply_jam_segments,
    calculate_output_frame_count,
    export_annotations,
    generate_random_segments,
    load_project,
    save_project,
)
from .models import SYNTHETIC_LABEL, JamMode, JamSegment, ProjectState, VideoInfo
from .paths import app_dir, default_projects_dir, runtime_ffmpeg_path
from .video_io import encode_video_ffmpeg, encode_video_opencv, extract_frames, read_video_info


class WorkerThread(QThread):
    progress_changed = Signal(int, int, str)
    message = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, task: Callable[[Callable[[int, int, str], None], Callable[[], bool]], str]) -> None:
        super().__init__()
        self._task = task
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            result = self._task(self.progress_changed.emit, lambda: self._cancelled)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)


class PreviewLabel(QLabel):
    roi_changed = Signal(tuple)

    def __init__(self) -> None:
        super().__init__("未加载视频")
        self.setMinimumSize(640, 360)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background:#121820;color:#E5EEF7;border:1px solid #2B3848;")
        self._pixmap: QPixmap | None = None
        self._image_size: tuple[int, int] | None = None
        self._roi: tuple[int, int, int, int] | None = None
        self._drag_start: QPoint | None = None
        self._drag_current: QPoint | None = None

    def set_frame(self, frame_bgr: np.ndarray | None) -> None:
        if frame_bgr is None:
            self._pixmap = None
            self._image_size = None
            self.setText("未加载视频")
            self.update()
            return
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        image = QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()
        self._pixmap = QPixmap.fromImage(image)
        self._image_size = (width, height)
        self.setText("")
        self.update()

    def set_roi(self, roi: tuple[int, int, int, int] | None) -> None:
        self._roi = roi
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if not self._pixmap:
            return
        painter = QPainter(self)
        target = self._target_rect()
        painter.drawPixmap(target, self._pixmap)
        pen = QPen(Qt.GlobalColor.cyan, 2)
        painter.setPen(pen)
        if self._roi and self._image_size:
            painter.drawRect(self._image_to_widget_rect(self._roi))
        if self._drag_start and self._drag_current:
            painter.setPen(QPen(Qt.GlobalColor.yellow, 2, Qt.PenStyle.DashLine))
            painter.drawRect(QRect(self._drag_start, self._drag_current).normalized())

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap:
            self._drag_start = event.position().toPoint()
            self._drag_current = self._drag_start
            self.update()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_start:
            self._drag_current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() != Qt.MouseButton.LeftButton or not self._drag_start or not self._image_size:
            return
        self._drag_current = event.position().toPoint()
        widget_rect = QRect(self._drag_start, self._drag_current).normalized()
        self._drag_start = None
        self._drag_current = None
        roi = self._widget_to_image_rect(widget_rect)
        if roi and roi[2] - roi[0] >= 2 and roi[3] - roi[1] >= 2:
            self._roi = roi
            self.roi_changed.emit(roi)
        self.update()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.update()

    def _target_rect(self) -> QRect:
        if not self._pixmap:
            return self.rect()
        scaled = self._pixmap.size()
        scaled.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def _widget_to_image_rect(self, rect: QRect) -> tuple[int, int, int, int] | None:
        if not self._image_size:
            return None
        target = self._target_rect()
        clipped = rect.intersected(target)
        if clipped.isEmpty():
            return None
        width, height = self._image_size
        sx = width / target.width()
        sy = height / target.height()
        x1 = int((clipped.left() - target.left()) * sx)
        y1 = int((clipped.top() - target.top()) * sy)
        x2 = int((clipped.right() - target.left() + 1) * sx)
        y2 = int((clipped.bottom() - target.top() + 1) * sy)
        return max(0, x1), max(0, y1), min(width, x2), min(height, y2)

    def _image_to_widget_rect(self, roi: tuple[int, int, int, int]) -> QRect:
        target = self._target_rect()
        width, height = self._image_size or (1, 1)
        x1, y1, x2, y2 = roi
        return QRect(
            target.left() + int(x1 * target.width() / width),
            target.top() + int(y1 * target.height() / height),
            max(1, int((x2 - x1) * target.width() / width)),
            max(1, int((y2 - y1) * target.height() / height)),
        )


class SegmentDialog(QDialog):
    def __init__(
        self,
        *,
        fps: float,
        frame_count: int,
        next_id: int,
        roi: tuple[int, int, int, int] | None,
        segment: JamSegment | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑堵塞片段")
        self._fps = fps
        max_time = max(0.0, (frame_count - 1) / fps) if fps > 0 else 0.0
        layout = QFormLayout(self)
        self.id_box = QSpinBox()
        self.id_box.setRange(1, 999999)
        self.id_box.setValue(segment.jam_id if segment else next_id)
        self.mode_box = QComboBox()
        self.mode_box.addItem("整帧冻结", JamMode.FULL_FREEZE.value)
        self.mode_box.addItem("ROI 局部冻结", JamMode.ROI_FREEZE.value)
        self.source_start = self._time_spin(max_time)
        self.source_end = self._time_spin(max_time)
        self.target_start = self._time_spin(max_time)
        self.target_end = self._time_spin(max_time)
        self.enabled_box = QCheckBox("启用")
        self.enabled_box.setChecked(True)
        self.roi_edit = QLineEdit(",".join(str(v) for v in roi) if roi else "")
        self.roi_edit.setPlaceholderText("x1,y1,x2,y2")

        if segment:
            index = self.mode_box.findData(segment.mode.value)
            self.mode_box.setCurrentIndex(index)
            self.source_start.setValue(segment.source_start_frame / fps)
            self.source_end.setValue(segment.source_end_frame / fps)
            self.target_start.setValue(segment.target_start_frame / fps)
            self.target_end.setValue(segment.target_end_frame / fps)
            self.enabled_box.setChecked(segment.enabled)
            self.roi_edit.setText(",".join(str(v) for v in segment.roi or roi or ()))

        layout.addRow("jam_id", self.id_box)
        layout.addRow("模式", self.mode_box)
        layout.addRow("来源开始秒", self.source_start)
        layout.addRow("来源结束秒", self.source_end)
        layout.addRow("目标开始秒", self.target_start)
        layout.addRow("目标结束秒", self.target_end)
        layout.addRow("ROI", self.roi_edit)
        layout.addRow("", self.enabled_box)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def segment(self) -> JamSegment:
        roi = None
        text = self.roi_edit.text().strip()
        if text:
            parts = [int(part.strip()) for part in text.split(",")]
            if len(parts) != 4:
                raise ValueError("ROI 必须是 x1,y1,x2,y2")
            roi = tuple(parts)
        mode = JamMode(self.mode_box.currentData())
        source_start_frame = int(round(self.source_start.value() * self._fps))
        source_end_frame = int(round(self.source_end.value() * self._fps))
        target_start_frame = int(round(self.target_start.value() * self._fps))
        target_end_frame = int(round(self.target_end.value() * self._fps))
        if mode == JamMode.FULL_FREEZE:
            source_start_frame = target_start_frame
            source_end_frame = target_start_frame
        return JamSegment(
            jam_id=self.id_box.value(),
            mode=mode,
            source_start_frame=source_start_frame,
            source_end_frame=source_end_frame,
            target_start_frame=target_start_frame,
            target_end_frame=target_end_frame,
            roi=roi,
            enabled=self.enabled_box.isChecked(),
        )

    def _time_spin(self, max_time: float) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(0.0, max_time)
        box.setDecimals(3)
        box.setSingleStep(0.1)
        return box


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CVDS 包裹堵塞视频合成工具")
        self.resize(1480, 920)
        self.video_path: Path | None = None
        self.video_info: VideoInfo | None = None
        self.project_dir: Path = default_projects_dir() / time.strftime("%Y%m%d_%H%M%S")
        self.output_dir: Path = self.project_dir / "output"
        self.frames_dir: Path = self.project_dir / "frames"
        self.synthetic_frames_dir: Path = self.project_dir / "synthetic_frames"
        self.segments: list[JamSegment] = []
        self.roi: tuple[int, int, int, int] | None = None
        self.current_frame = 0
        self.extracted_frame_count = 0
        self.synthetic_frame_count = 0
        self.worker: WorkerThread | None = None
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.next_frame)
        self.logger = logging.getLogger("cvds_jam_video_synthesizer")

        self._build_ui()
        self._setup_logger()
        self._refresh_paths()
        self.append_log(f"输出会明确标记为 {SYNTHETIC_LABEL}")

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._project_panel())
        splitter.addWidget(self._preview_panel())
        splitter.addWidget(self._settings_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        root.addWidget(splitter, 4)
        root.addWidget(self._segments_panel(), 2)
        root.addWidget(self._bottom_panel(), 1)
        self.setCentralWidget(central)
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        self.menuBar().addMenu("文件").addAction(exit_action)

    def _project_panel(self) -> QWidget:
        box = QGroupBox("项目")
        layout = QVBoxLayout(box)
        self.video_edit = QLineEdit()
        self.video_edit.setReadOnly(True)
        self.project_edit = QLineEdit()
        self.project_edit.setReadOnly(True)
        self.info_label = QLabel("未读取视频")
        self.info_label.setWordWrap(True)
        self.extract_mode = QComboBox()
        self.extract_mode.addItem("按原始 FPS 抽帧", 0)
        self.extract_mode.addItem("每秒抽 N 帧", 1)
        self.extract_n = QSpinBox()
        self.extract_n.setRange(1, 120)
        self.extract_n.setValue(5)
        choose_video = QPushButton("选择视频")
        choose_video.clicked.connect(self.choose_video)
        choose_project = QPushButton("选择项目目录")
        choose_project.clicked.connect(self.choose_project_dir)
        extract = QPushButton("抽帧")
        extract.clicked.connect(self.extract_frames_task)
        open_output = QPushButton("打开输出目录")
        open_output.clicked.connect(lambda: self.open_dir(self.output_dir))
        layout.addWidget(QLabel("视频文件"))
        layout.addWidget(self.video_edit)
        layout.addWidget(choose_video)
        layout.addWidget(QLabel("项目目录"))
        layout.addWidget(self.project_edit)
        layout.addWidget(choose_project)
        layout.addWidget(self.info_label)
        layout.addWidget(self.extract_mode)
        layout.addWidget(self.extract_n)
        layout.addWidget(extract)
        layout.addWidget(open_output)
        layout.addStretch(1)
        return box

    def _preview_panel(self) -> QWidget:
        box = QGroupBox("预览与 ROI")
        layout = QVBoxLayout(box)
        self.preview = PreviewLabel()
        self.preview.roi_changed.connect(self.on_roi_changed)
        controls = QHBoxLayout()
        previous_btn = QPushButton("上一帧")
        previous_btn.clicked.connect(self.previous_frame)
        self.play_btn = QPushButton("播放")
        self.play_btn.clicked.connect(self.toggle_play)
        next_btn = QPushButton("下一帧")
        next_btn.clicked.connect(self.next_frame)
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.valueChanged.connect(self.seek_frame)
        self.frame_label = QLabel("0 / 0")
        controls.addWidget(previous_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(next_btn)
        controls.addWidget(self.frame_slider, 1)
        controls.addWidget(self.frame_label)
        layout.addWidget(self.preview, 1)
        layout.addLayout(controls)
        return box

    def _settings_panel(self) -> QWidget:
        box = QGroupBox("参数")
        layout = QFormLayout(box)
        self.mode_box = QComboBox()
        self.mode_box.addItem("整帧冻结", JamMode.FULL_FREEZE.value)
        self.mode_box.addItem("ROI 局部冻结", JamMode.ROI_FREEZE.value)
        self.random_count = QSpinBox()
        self.random_count.setRange(0, 999)
        self.random_count.setValue(3)
        self.min_duration = QDoubleSpinBox()
        self.min_duration.setRange(0.1, 3600)
        self.min_duration.setValue(10.0)
        self.max_duration = QDoubleSpinBox()
        self.max_duration.setRange(0.1, 3600)
        self.max_duration.setValue(30.0)
        self.seed_box = QSpinBox()
        self.seed_box.setRange(0, 2147483647)
        self.seed_box.setValue(20260601)
        self.brightness_box = QCheckBox("亮度扰动")
        self.noise_box = QCheckBox("噪声扰动")
        self.position_box = QCheckBox("位置扰动")
        random_btn = QPushButton("生成随机片段")
        random_btn.clicked.connect(self.generate_random)
        layout.addRow("堵塞模式", self.mode_box)
        layout.addRow("片段数量", self.random_count)
        layout.addRow("最小时长秒", self.min_duration)
        layout.addRow("最大时长秒", self.max_duration)
        layout.addRow("随机种子", self.seed_box)
        layout.addRow("高级设置", self.brightness_box)
        layout.addRow("", self.noise_box)
        layout.addRow("", self.position_box)
        layout.addRow(random_btn)
        return box

    def _segments_panel(self) -> QWidget:
        box = QGroupBox("堵塞片段")
        layout = QVBoxLayout(box)
        self.segment_table = QTableWidget(0, 9)
        self.segment_table.setHorizontalHeaderLabels(
            ["启用", "ID", "模式", "来源秒", "目标秒", "来源帧", "目标帧", "ROI", "标记"]
        )
        self.segment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.segment_table.itemSelectionChanged.connect(self.on_segment_selected)
        buttons = QHBoxLayout()
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.add_segment)
        edit_btn = QPushButton("修改")
        edit_btn.clicked.connect(self.edit_segment)
        delete_btn = QPushButton("删除")
        delete_btn.clicked.connect(self.delete_segment)
        toggle_btn = QPushButton("启用/禁用")
        toggle_btn.clicked.connect(self.toggle_segment_enabled)
        for button in (add_btn, edit_btn, delete_btn, toggle_btn):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addWidget(self.segment_table)
        layout.addLayout(buttons)
        return box

    def _bottom_panel(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        actions = QHBoxLayout()
        preview_btn = QPushButton("生成预览")
        preview_btn.clicked.connect(self.preview_selected_segment)
        generate_btn = QPushButton("生成全部帧")
        generate_btn.clicked.connect(self.generate_all_frames_task)
        encode_btn = QPushButton("合成视频")
        encode_btn.clicked.connect(self.encode_video_task)
        save_btn = QPushButton("保存项目")
        save_btn.clicked.connect(self.save_project_file)
        load_btn = QPushButton("加载项目")
        load_btn.clicked.connect(self.load_project_file)
        cancel_btn = QPushButton("取消任务")
        cancel_btn.clicked.connect(self.cancel_task)
        for button in (preview_btn, generate_btn, encode_btn, save_btn, load_btn, cancel_btn):
            actions.addWidget(button)
        self.progress = QProgressBar()
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(150)
        layout.addLayout(actions)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_box)
        return box

    def _setup_logger(self) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        log_dir = self.project_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.logger.handlers.clear()
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(handler)

    def append_log(self, text: str) -> None:
        self.log_box.append(text)
        self.logger.info(text)

    def show_error(self, text: str) -> None:
        self.append_log(f"错误：{text}")
        QMessageBox.critical(self, "错误", text)

    def _refresh_paths(self) -> None:
        self.output_dir = self.project_dir / "output"
        self.frames_dir = self.project_dir / "frames"
        self.synthetic_frames_dir = self.project_dir / "synthetic_frames"
        self.project_edit.setText(str(self.project_dir))

    def choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择正常包裹运输视频",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv)",
        )
        if not path:
            return
        try:
            self.video_path = Path(path)
            self.video_info = read_video_info(self.video_path)
            self.video_edit.setText(str(self.video_path))
            self.info_label.setText(self._video_info_text())
            self.frame_slider.setRange(0, max(0, self.video_info.frame_count - 1))
            self.show_frame(0)
            self.append_log("视频读取成功")
        except Exception as exc:  # noqa: BLE001
            self.show_error(str(exc))

    def choose_project_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择项目目录", str(default_projects_dir()))
        if not path:
            return
        self.project_dir = Path(path)
        self._refresh_paths()
        self._setup_logger()
        self.append_log("项目目录已更新")

    def _video_info_text(self) -> str:
        if not self.video_info:
            return "未读取视频"
        return (
            f"FPS: {self.video_info.fps:.3f}\n"
            f"分辨率: {self.video_info.width}x{self.video_info.height}\n"
            f"总帧数: {self.video_info.frame_count}\n"
            f"时长: {self.video_info.duration_sec:.3f} 秒"
        )

    def show_frame(self, index: int) -> None:
        if not self.video_path or not self.video_info:
            return
        index = max(0, min(index, self.video_info.frame_count - 1))
        capture = cv2.VideoCapture(str(self.video_path))
        try:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("当前帧读取失败")
            self.current_frame = index
            self.preview.set_frame(frame)
            self.preview.set_roi(self.roi)
            self.frame_slider.blockSignals(True)
            self.frame_slider.setValue(index)
            self.frame_slider.blockSignals(False)
            self.frame_label.setText(f"{index} / {self.video_info.frame_count - 1}")
        except Exception as exc:  # noqa: BLE001
            self.show_error(str(exc))
        finally:
            capture.release()

    def seek_frame(self, value: int) -> None:
        self.show_frame(value)

    def previous_frame(self) -> None:
        self.show_frame(self.current_frame - 1)

    def next_frame(self) -> None:
        self.show_frame(self.current_frame + 1)

    def toggle_play(self) -> None:
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.play_btn.setText("播放")
            return
        if not self.video_info:
            self.show_error("请先导入视频")
            return
        interval = max(20, int(1000 / min(self.video_info.fps, 15)))
        self.play_timer.start(interval)
        self.play_btn.setText("暂停")

    def on_roi_changed(self, roi: tuple[int, int, int, int]) -> None:
        self.roi = roi
        self.append_log(f"ROI 已设置：{roi}")

    def generate_random(self) -> None:
        working_info = self._working_video_info()
        if not working_info:
            self.show_error("请先导入视频")
            return
        try:
            new_segments = generate_random_segments(
                video_info=working_info,
                count=self.random_count.value(),
                min_duration_sec=self.min_duration.value(),
                max_duration_sec=self.max_duration.value(),
                seed=self.seed_box.value(),
                mode=JamMode(self.mode_box.currentData()),
                roi=self.roi,
            )
            self.segments = new_segments
            self.refresh_segments_table()
            self.append_log("随机堵塞片段已生成")
        except Exception as exc:  # noqa: BLE001
            self.show_error(str(exc))

    def add_segment(self) -> None:
        if not self.video_info:
            self.show_error("请先导入视频")
            return
        dialog = SegmentDialog(
            fps=self.video_info.fps,
            frame_count=self.video_info.frame_count,
            next_id=self._next_segment_id(),
            roi=self.roi,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.segments.append(dialog.segment())
            self.refresh_segments_table()
        except Exception as exc:  # noqa: BLE001
            self.show_error(str(exc))

    def edit_segment(self) -> None:
        row = self.segment_table.currentRow()
        if row < 0 or not self.video_info:
            self.show_error("请先选择片段")
            return
        dialog = SegmentDialog(
            fps=self.video_info.fps,
            frame_count=self.video_info.frame_count,
            next_id=self._next_segment_id(),
            roi=self.roi,
            segment=self.segments[row],
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.segments[row] = dialog.segment()
            self.refresh_segments_table()
        except Exception as exc:  # noqa: BLE001
            self.show_error(str(exc))

    def delete_segment(self) -> None:
        row = self.segment_table.currentRow()
        if row < 0:
            return
        del self.segments[row]
        self.refresh_segments_table()

    def toggle_segment_enabled(self) -> None:
        row = self.segment_table.currentRow()
        if row < 0:
            return
        segment = self.segments[row]
        self.segments[row] = JamSegment(
            jam_id=segment.jam_id,
            mode=segment.mode,
            source_start_frame=segment.source_start_frame,
            source_end_frame=segment.source_end_frame,
            target_start_frame=segment.target_start_frame,
            target_end_frame=segment.target_end_frame,
            roi=segment.roi,
            enabled=not segment.enabled,
        )
        self.refresh_segments_table()

    def on_segment_selected(self) -> None:
        row = self.segment_table.currentRow()
        if row >= 0 and row < len(self.segments):
            self.show_frame(max(0, self.segments[row].target_start_frame - 5))

    def refresh_segments_table(self) -> None:
        working_info = self._working_video_info()
        fps = working_info.fps if working_info else 1.0
        self.segment_table.setRowCount(len(self.segments))
        for row, segment in enumerate(self.segments):
            source_time = f"{segment.source_start_frame / fps:.3f}-{segment.source_end_frame / fps:.3f}"
            target_time = f"{segment.target_start_frame / fps:.3f}-{segment.target_end_frame / fps:.3f}"
            values = [
                "是" if segment.enabled else "否",
                str(segment.jam_id),
                "整帧冻结" if segment.mode == JamMode.FULL_FREEZE else "ROI 局部冻结",
                source_time,
                target_time,
                f"{segment.source_start_frame}-{segment.source_end_frame}",
                f"{segment.target_start_frame}-{segment.target_end_frame}",
                ",".join(str(v) for v in segment.roi) if segment.roi else "",
                SYNTHETIC_LABEL,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.segment_table.setItem(row, column, item)

    def preview_selected_segment(self) -> None:
        row = self.segment_table.currentRow()
        if row < 0 or not self.video_path:
            self.show_error("请先选择片段")
            return
        segment = self.segments[row]
        try:
            target_frame = self._read_video_frame(segment.target_start_frame)
            source_frame = self._read_video_frame(segment.source_start_frame)
            if segment.mode == JamMode.FULL_FREEZE:
                preview = source_frame
            else:
                if not segment.roi:
                    raise ValueError("ROI 局部冻结模式必须设置 ROI")
                x1, y1, x2, y2 = segment.roi
                preview = target_frame.copy()
                preview[y1:y2, x1:x2] = source_frame[y1:y2, x1:x2]
            self.preview.set_frame(preview)
            self.preview.set_roi(segment.roi or self.roi)
            self.append_log("已生成当前片段预览")
        except Exception as exc:  # noqa: BLE001
            self.show_error(str(exc))

    def _read_video_frame(self, frame_index: int) -> np.ndarray:
        if not self.video_path:
            raise RuntimeError("请先导入视频")
        capture = cv2.VideoCapture(str(self.video_path))
        try:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("视频帧读取失败")
            return frame
        finally:
            capture.release()

    def extract_frames_task(self) -> None:
        if not self.video_path:
            self.show_error("请先导入视频")
            return
        every_n = self.extract_n.value() if self.extract_mode.currentData() == 1 else None

        def task(progress, cancelled) -> str:
            count = extract_frames(self.video_path, self.frames_dir, every_n_per_second=every_n, progress=progress, cancelled=cancelled)
            self.extracted_frame_count = count
            self.synthetic_frame_count = 0
            return f"抽帧完成：{count} 张"

        self.start_task(task)

    def generate_all_frames_task(self) -> None:
        working_info = self._working_video_info()
        if not working_info:
            self.show_error("请先导入视频")
            return
        frame_count = working_info.frame_count
        brightness_jitter = self.brightness_box.isChecked()
        noise_jitter = self.noise_box.isChecked()
        position_jitter = self.position_box.isChecked()
        seed = self.seed_box.value()

        def task(progress, cancelled) -> str:
            output_count = apply_jam_segments(
                self.frames_dir,
                self.synthetic_frames_dir,
                self.segments,
                frame_count=frame_count,
                brightness_jitter=brightness_jitter,
                noise_jitter=noise_jitter,
                position_jitter=position_jitter,
                seed=seed,
                progress=progress,
                cancelled=cancelled,
            )
            self.synthetic_frame_count = output_count
            output_info = VideoInfo(
                fps=working_info.fps,
                width=working_info.width,
                height=working_info.height,
                frame_count=output_count,
            )
            export_annotations(self.output_dir, self.segments, output_info)
            return f"合成帧完成：{output_count} 张，标注已写入：{self.output_dir}"

        self.start_task(task)

    def encode_video_task(self) -> None:
        working_info = self._working_video_info()
        if not working_info:
            self.show_error("请先导入视频")
            return
        frame_count = self.synthetic_frame_count or calculate_output_frame_count(working_info.frame_count, self.segments)
        output_path = self.output_dir / "jam_video.mp4"
        output_info = VideoInfo(
            fps=working_info.fps,
            width=working_info.width,
            height=working_info.height,
            frame_count=frame_count,
        )

        def task(progress, cancelled) -> str:
            ffmpeg = runtime_ffmpeg_path()
            if ffmpeg.exists():
                encode_video_ffmpeg(self.synthetic_frames_dir, output_path, fps=working_info.fps, ffmpeg_path=ffmpeg)
            else:
                encode_video_opencv(
                    self.synthetic_frames_dir,
                    output_path,
                    fps=working_info.fps,
                    width=working_info.width,
                    height=working_info.height,
                    frame_count=frame_count,
                    progress=progress,
                    cancelled=cancelled,
                )
            export_annotations(self.output_dir, self.segments, output_info)
            return f"视频已导出：{output_path}，类型：{SYNTHETIC_LABEL}"

        self.start_task(task)

    def start_task(self, task: Callable[[Callable[[int, int, str], None], Callable[[], bool]], str]) -> None:
        if self.worker and self.worker.isRunning():
            self.show_error("已有任务正在运行")
            return
        self.progress.setValue(0)
        self.worker = WorkerThread(task)
        self.worker.progress_changed.connect(self.on_progress)
        self.worker.succeeded.connect(self.on_task_success)
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()
        self.append_log("后台任务已启动")

    def on_progress(self, value: int, total: int, text: str) -> None:
        percent = 0 if total <= 0 else int(value * 100 / total)
        self.progress.setValue(max(0, min(100, percent)))
        if value == total or value % 50 == 0:
            self.append_log(f"{text}：{value}/{total}")

    def on_task_success(self, text: str) -> None:
        self.progress.setValue(100)
        self.append_log(text)

    def on_task_failed(self, text: str) -> None:
        self.progress.setValue(0)
        self.show_error(text)

    def cancel_task(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.append_log("正在取消任务")

    def save_project_file(self) -> None:
        path = self.project_dir / "project.json"
        try:
            save_project(path, self._project_state())
            self.append_log(f"项目已保存：{path}")
        except Exception as exc:  # noqa: BLE001
            self.show_error(str(exc))

    def load_project_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "加载项目", str(default_projects_dir()), "Project (*.json)")
        if not path:
            return
        try:
            state = load_project(Path(path))
            self.video_path = Path(state.video_path) if state.video_path else None
            self.project_dir = Path(state.project_dir) if state.project_dir else Path(path).parent
            self._refresh_paths()
            self._setup_logger()
            self.roi = state.roi
            self.segments = state.segments
            self.seed_box.setValue(state.random_seed)
            self.random_count.setValue(state.random_count)
            self.min_duration.setValue(state.random_min_duration)
            self.max_duration.setValue(state.random_max_duration)
            self.brightness_box.setChecked(state.brightness_jitter)
            self.noise_box.setChecked(state.noise_jitter)
            self.position_box.setChecked(state.position_jitter)
            if self.video_path and self.video_path.exists():
                self.video_info = read_video_info(self.video_path)
                self.video_edit.setText(str(self.video_path))
                self.info_label.setText(self._video_info_text())
                self.frame_slider.setRange(0, max(0, self.video_info.frame_count - 1))
                self.show_frame(0)
            self.refresh_segments_table()
            self.append_log("项目已加载")
        except Exception as exc:  # noqa: BLE001
            self.show_error(str(exc))

    def _project_state(self) -> ProjectState:
        return ProjectState(
            video_path=str(self.video_path or ""),
            project_dir=str(self.project_dir),
            output_dir=str(self.output_dir),
            extracted=self.frames_dir.exists(),
            roi=self.roi,
            random_seed=self.seed_box.value(),
            random_count=self.random_count.value(),
            random_min_duration=self.min_duration.value(),
            random_max_duration=self.max_duration.value(),
            brightness_jitter=self.brightness_box.isChecked(),
            noise_jitter=self.noise_box.isChecked(),
            position_jitter=self.position_box.isChecked(),
            segments=self.segments,
        )

    def _working_video_info(self) -> VideoInfo | None:
        if not self.video_info:
            return None
        if self.extracted_frame_count > 0 and self.extract_mode.currentData() == 1:
            return VideoInfo(
                fps=float(self.extract_n.value()),
                width=self.video_info.width,
                height=self.video_info.height,
                frame_count=self.extracted_frame_count,
            )
        return self.video_info

    def _next_segment_id(self) -> int:
        return max((segment.jam_id for segment in self.segments), default=0) + 1

    def open_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # type: ignore[attr-defined]


def main() -> int:
    if "--version" in sys.argv:
        print(__version__)
        return 0
    if "--diagnose" in sys.argv:
        payload = {
            "ok": True,
            "version": __version__,
            "app_dir": str(app_dir()),
            "default_projects_dir": str(default_projects_dir()),
            "ffmpeg_exists": runtime_ffmpeg_path().exists(),
            "data_type": SYNTHETIC_LABEL,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    if "--window-smoke-test" in sys.argv and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv)
    window = MainWindow()
    if "--window-smoke-test" in sys.argv:
        window.close()
        app.processEvents()
        return 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
