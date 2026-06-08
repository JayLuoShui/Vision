"""
CVDS AI 辅助 YOLO 标注工具 v2

特性：
- 检测框 + 分割多边形双模式（YOLO det / seg 格式自动识别与读写）
- 滚轮缩放（以鼠标为锚点）+ 中键 / Ctrl+左键拖拽 + 双击重置视图
- 完整键盘流：A/D 翻页，PgUp/PgDn 跳 10 张，Home/End，Space 保存，
  Delete 删框，Ctrl+D 删图，Ctrl+E 跳下一个空标注，Ctrl+G 聚焦跳转框，
  Esc 撤回当前标注动作，Q/E 上一/下一类别，0-9 选类，Shift+0-9 修改选中标注的类别
- 快速跳转：按行号或文件名片段
- 一键负样本过滤（只看 0 框图片）
- 扫描时自动为没有标签的图片生成空 .txt（负样本闭环）
- 删除当前图片后自动跳到下一张
- QSettings 持久化：路径、AI 参数、视频参数、模式、窗口尺寸、splitter、
  上次浏览索引
- 启动加速：ultralytics / OpenCV / Numpy 延迟导入；标签编辑 debounce；启动不强制写盘
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
import uuid


DLL_DIRECTORY_HANDLES: list[object] = []
AI_PYTHON = Path(r"C:\Users\shuai\anaconda3\envs\AI\python.exe")


def relaunch_source_with_ai_python() -> None:
    if getattr(sys, "frozen", False):
        return
    if os.environ.get("CVDS_NO_AI_RELAUNCH"):
        return
    try:
        launched_script = Path(sys.argv[0]).resolve()
        current_script = Path(__file__).resolve()
        current_python = Path(sys.executable).resolve()
    except OSError:
        return
    if launched_script != current_script:
        return
    if AI_PYTHON.exists() and current_python != AI_PYTHON.resolve():
        os.environ["CVDS_NO_AI_RELAUNCH"] = "1"
        os.execv(str(AI_PYTHON), [str(AI_PYTHON), str(current_script), *sys.argv[1:]])


def configure_qt_runtime_paths() -> None:
    """Make PySide6 work when launched as source or from the PyInstaller folder."""
    executable_dir = Path(sys.executable).resolve().parent
    source_dir = Path(__file__).resolve().parent
    bundled_internal = source_dir / "CVDS_Annotation_Tool_v2" / "_internal"
    frozen_internal = Path(getattr(sys, "_MEIPASS", executable_dir / "_internal"))
    is_frozen = bool(getattr(sys, "frozen", False))
    bundled_candidates = [
        frozen_internal / "PySide6",
        frozen_internal / "shiboken6",
        frozen_internal,
        executable_dir / "_internal" / "PySide6",
        executable_dir / "_internal" / "shiboken6",
        executable_dir / "_internal",
        bundled_internal / "PySide6",
        bundled_internal / "shiboken6",
        bundled_internal,
    ]
    env_candidates = [
        Path(sys.prefix) / "Lib" / "site-packages" / "PySide6",
        Path(sys.prefix) / "Lib" / "site-packages" / "shiboken6",
        Path(sys.prefix) / "Library" / "bin",
    ]
    candidates = bundled_candidates if is_frozen else env_candidates

    valid_paths: list[str] = []
    for candidate in candidates:
        if not candidate.exists():
            continue
        path_text = str(candidate)
        if candidate.name == "_internal" and path_text not in sys.path:
            sys.path.insert(0, path_text)
        if is_frozen and candidate.name == "_internal":
            continue
        if path_text not in valid_paths:
            valid_paths.append(path_text)
        if hasattr(os, "add_dll_directory"):
            try:
                DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(path_text))
            except OSError:
                pass

    if valid_paths:
        existing_path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join(valid_paths + [existing_path])

    for base in (bundled_internal, frozen_internal, executable_dir / "_internal"):
        plugins = base / "PySide6" / "plugins"
        platforms = plugins / "platforms"
        if plugins.exists():
            os.environ.setdefault("QT_PLUGIN_PATH", str(plugins))
        if platforms.exists():
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(platforms))


relaunch_source_with_ai_python()
configure_qt_runtime_paths()

import yaml
from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    QPoint,
    QPointF,
    QRectF,
    QSettings,
    Qt,
    QThread,
    QTimer,
    Signal,
    qVersion,
)
from PySide6.QtGui import (
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    import numpy as np


# ====================================================================
# 常量
# ====================================================================

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".m4v", ".flv"}

BOX_COLORS = [
    QColor("#00E5FF"),
    QColor("#FFB000"),
    QColor("#39FF14"),
    QColor("#FF4FD8"),
    QColor("#7C4DFF"),
    QColor("#FF7043"),
    QColor("#00C853"),
    QColor("#29B6F6"),
]
SELECTED_COLOR = QColor("#00E5FF")
TEXT_BG = QColor(22, 28, 38, 220)
DEFECT_META_VERSION = 1
DEFECT_TYPES = ("hole", "crack", "tear", "dent", "contamination", "other")
DEFECT_TYPE_LABELS = {
    "hole": "洞 / hole",
    "crack": "裂纹 / crack",
    "tear": "破损 / tear",
    "dent": "凹陷 / dent",
    "contamination": "污渍 / contamination",
    "other": "其他 / other",
}
DEFECT_SEVERITIES = ("low", "medium", "high")
DEFECT_SEVERITY_LABELS = {
    "low": "轻微",
    "medium": "中等",
    "high": "严重",
}
DEFECT_COLORS = {
    "hole": QColor("#ff4f64"),
    "crack": QColor("#ffd166"),
    "tear": QColor("#ff8a4c"),
    "dent": QColor("#8bd3ff"),
    "contamination": QColor("#9be564"),
    "other": QColor("#c7a6ff"),
}

SETTINGS_ORG = "CVDS"
SETTINGS_APP = "AnnoToolV2"
_CUDA_DEVICE_NAME: str | None = None
_CUDA_DEVICE_CHECKED = False

VSCODE_DARK_QSS = """
QWidget {
    background-color: #111318;
    color: #e5e7eb;
    font-family: "Microsoft YaHei UI", "Segoe UI", Arial;
    font-size: 12px;
}
QMainWindow, QStatusBar {
    background-color: #0f1117;
}
QStatusBar {
    border-top: 1px solid #2a2f3a;
    color: #8bd3ff;
}
QSplitter::handle {
    background-color: #242936;
    margin: 0 2px;
}
QScrollArea {
    background-color: #151923;
    border: 1px solid #2a2f3a;
    border-radius: 6px;
}
QWidget#LeftPanel {
    background-color: #151923;
}
QWidget#RightPanel {
    background-color: #111318;
}
QGroupBox {
    background-color: #171b25;
    border: 1px solid #2f3746;
    border-radius: 6px;
    margin-top: 16px;
    padding: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #7dd3fc;
    font-weight: 600;
}
QLabel {
    color: #e5e7eb;
    background: transparent;
}
QLabel#InfoLabel {
    background-color: #172033;
    border: 1px solid #2f3c55;
    border-left: 3px solid #22c55e;
    border-radius: 5px;
    color: #e5e7eb;
}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #0b0f16;
    border: 1px solid #2f3746;
    border-radius: 5px;
    color: #e5e7eb;
    min-height: 26px;
    padding: 2px 8px;
    selection-background-color: #264f78;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #60a5fa;
}
QComboBox {
    padding-right: 34px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    background-color: #1d4ed8;
    border-left: 1px solid #60a5fa;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    width: 28px;
}
QComboBox::drop-down:hover {
    background-color: #2563eb;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #ffffff;
    width: 0;
    height: 0;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #202638;
    border-left: 1px solid #2f3746;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #171b25;
    border: 1px solid #2f3746;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
    color: #d7dde8;
}
QPushButton {
    background-color: #1d4ed8;
    border: 1px solid #60a5fa;
    border-radius: 5px;
    color: #ffffff;
    min-height: 28px;
    padding: 3px 8px;
}
QPushButton:hover {
    background-color: #2563eb;
}
QPushButton:pressed {
    background-color: #1e40af;
}
QPushButton:disabled {
    background-color: #20242d;
    border-color: #2f3746;
    color: #778091;
}
QCheckBox {
    background: transparent;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #596579;
    background: #0b0f16;
}
QCheckBox::indicator:checked {
    background: #22c55e;
    border: 1px solid #22c55e;
}
QListView, QTableWidget {
    background-color: #0b0f16;
    alternate-background-color: #151b29;
    border: 1px solid #2f3746;
    gridline-color: #242936;
    selection-background-color: #1e3a5f;
    selection-color: #ffffff;
}
QHeaderView::section {
    background-color: #1b2230;
    border: 0;
    border-right: 1px solid #2f3746;
    border-bottom: 1px solid #2f3746;
    color: #f8d66d;
    padding: 4px;
}
QProgressBar {
    background-color: #0b0f16;
    border: 1px solid #2f3746;
    border-radius: 5px;
    color: #e5e7eb;
    min-height: 18px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #22c55e;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: #111318;
    border: none;
    width: 12px;
    height: 12px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #374151;
    border-radius: 4px;
    min-height: 24px;
    min-width: 24px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #4b5563;
}
QScrollBar::add-line, QScrollBar::sub-line {
    height: 0;
    width: 0;
}
"""


def find_project_root() -> Path:
    if os.environ.get("CVDS_ROOT"):
        return Path(os.environ["CVDS_ROOT"]).resolve()
    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parents[1]
    for candidate in [start, *start.parents]:
        if (candidate / "weights").exists() or (candidate / "datasets").exists():
            return candidate
    return start


def detect_cuda_device_name() -> str | None:
    global _CUDA_DEVICE_CHECKED, _CUDA_DEVICE_NAME
    if _CUDA_DEVICE_CHECKED:
        return _CUDA_DEVICE_NAME
    _CUDA_DEVICE_CHECKED = True
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=1,
            creationflags=creation_flags,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    name = result.stdout.strip().splitlines()
    _CUDA_DEVICE_NAME = name[0].strip() if name and name[0].strip() else None
    return _CUDA_DEVICE_NAME


ROOT = find_project_root()
DEFAULT_WEIGHTS = ROOT / "weights" / "cvds_yolo26n_package_best.pt"
DEFAULT_OUTPUT = ROOT / "datasets" / "cvds_annotation_yolo"
DEFAULT_IMAGE_FOLDER = ROOT / "datasets" / "cvds_crossbelt_annotation_seed" / "images"
DEFAULT_VIDEO_FOLDER = ROOT


# ====================================================================
# 延迟导入 ultralytics（启动加速关键点）
# ====================================================================

_YOLO_CLS = None
_CV2_MODULE = None
_NP_MODULE = None


def get_yolo_cls():
    global _YOLO_CLS
    if _YOLO_CLS is None:
        from ultralytics import YOLO  # 延迟到真正用时再加载
        _YOLO_CLS = YOLO
    return _YOLO_CLS


def get_cv2():
    global _CV2_MODULE
    if _CV2_MODULE is None:
        import cv2
        _CV2_MODULE = cv2
    return _CV2_MODULE


def get_np():
    global _NP_MODULE
    if _NP_MODULE is None:
        import numpy as np
        _NP_MODULE = np
    return _NP_MODULE


# ====================================================================
# 数据模型
# ====================================================================


@dataclass
class Annotation:
    """统一标注：kind='box' 用两个角点，kind='polygon' 用任意多边形顶点。"""

    cls: int
    kind: str = "box"
    points: list[tuple[float, float]] = field(default_factory=list)
    conf: float | None = None

    @classmethod
    def from_box(cls_, cls_idx: int, x1: float, y1: float, x2: float, y2: float, conf: float | None = None) -> "Annotation":
        return Annotation(int(cls_idx), "box", [(float(x1), float(y1)), (float(x2), float(y2))], conf)

    @classmethod
    def from_polygon(cls_, cls_idx: int, points, conf: float | None = None) -> "Annotation":
        return Annotation(int(cls_idx), "polygon", [(float(x), float(y)) for x, y in points], conf)

    def copy(self) -> "Annotation":
        return Annotation(self.cls, self.kind, list(self.points), self.conf)

    @property
    def is_box(self) -> bool:
        return self.kind == "box"

    @property
    def is_polygon(self) -> bool:
        return self.kind == "polygon"

    def box_corners(self) -> tuple[float, float, float, float]:
        if not self.is_box or len(self.points) < 2:
            return 0.0, 0.0, 0.0, 0.0
        return self.points[0][0], self.points[0][1], self.points[1][0], self.points[1][1]

    def rect(self) -> QRectF:
        if not self.points:
            return QRectF()
        if self.is_box:
            x1, y1, x2, y2 = self.box_corners()
            left, right = sorted([x1, x2])
            top, bottom = sorted([y1, y2])
            return QRectF(left, top, right - left, bottom - top)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def contains(self, x: float, y: float) -> bool:
        if not self.points:
            return False
        if self.is_box:
            return self.rect().contains(QPointF(x, y))
        poly = QPolygonF([QPointF(px, py) for px, py in self.points])
        return poly.containsPoint(QPointF(x, y), Qt.OddEvenFill)

    def to_yolo_line(self, width: int, height: int) -> str | None:
        if width <= 0 or height <= 0:
            return None
        if self.is_box:
            x1, y1, x2, y2 = self.box_corners()
            x1 = max(0.0, min(float(width), x1))
            y1 = max(0.0, min(float(height), y1))
            x2 = max(0.0, min(float(width), x2))
            y2 = max(0.0, min(float(height), y2))
            left, right = sorted([x1, x2])
            top, bottom = sorted([y1, y2])
            bw = right - left
            bh = bottom - top
            if bw < 1.0 or bh < 1.0:
                return None
            cx = left + bw / 2.0
            cy = top + bh / 2.0
            return f"{self.cls} {cx / width:.6f} {cy / height:.6f} {bw / width:.6f} {bh / height:.6f}"
        if len(self.points) < 3:
            return None
        parts = [str(self.cls)]
        for x, y in self.points:
            x = max(0.0, min(float(width), x))
            y = max(0.0, min(float(height), y))
            parts.append(f"{x / width:.6f}")
            parts.append(f"{y / height:.6f}")
        return " ".join(parts)

    @staticmethod
    def from_yolo_line(line: str, width: int, height: int) -> "Annotation | None":
        parts = line.split()
        if len(parts) < 5:
            return None
        try:
            cls = int(float(parts[0]))
            values = [float(v) for v in parts[1:]]
        except ValueError:
            return None
        if len(values) == 4:
            cx, cy, bw, bh = values
            x1 = (cx - bw / 2.0) * width
            y1 = (cy - bh / 2.0) * height
            x2 = (cx + bw / 2.0) * width
            y2 = (cy + bh / 2.0) * height
            return Annotation.from_box(cls, x1, y1, x2, y2)
        if len(values) % 2 == 0 and len(values) >= 6:
            pts = [(values[i] * width, values[i + 1] * height) for i in range(0, len(values), 2)]
            return Annotation.from_polygon(cls, pts)
        return None


@dataclass
class DefectAnnotation:
    """目标内部缺陷层：独立保存，并通过 parent_index 绑定到一个包裹/目标实例。"""

    defect_id: str
    parent_index: int
    parent_cls: int
    defect_type: str = "hole"
    severity: str = "medium"
    points: list[tuple[float, float]] = field(default_factory=list)
    note: str = ""
    created_at: str = ""

    @classmethod
    def from_polygon(
        cls_,
        parent_index: int,
        parent: Annotation,
        defect_type: str,
        severity: str,
        points,
        note: str = "",
        defect_id: str | None = None,
        created_at: str | None = None,
    ) -> "DefectAnnotation":
        return DefectAnnotation(
            defect_id=defect_id or uuid.uuid4().hex[:12],
            parent_index=int(parent_index),
            parent_cls=int(parent.cls),
            defect_type=defect_type if defect_type in DEFECT_TYPES else "other",
            severity=severity if severity in DEFECT_SEVERITIES else "medium",
            points=[(float(x), float(y)) for x, y in points],
            note=note,
            created_at=created_at or datetime.now().isoformat(timespec="seconds"),
        )

    def copy(self) -> "DefectAnnotation":
        return DefectAnnotation(
            self.defect_id,
            self.parent_index,
            self.parent_cls,
            self.defect_type,
            self.severity,
            list(self.points),
            self.note,
            self.created_at,
        )

    def rect(self) -> QRectF:
        if not self.points:
            return QRectF()
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def contains(self, x: float, y: float) -> bool:
        if len(self.points) < 3:
            return False
        poly = QPolygonF([QPointF(px, py) for px, py in self.points])
        return poly.containsPoint(QPointF(x, y), Qt.OddEvenFill)

    def to_json(self, width: int, height: int, labels: list[str]) -> dict:
        parent_name = labels[self.parent_cls] if 0 <= self.parent_cls < len(labels) else str(self.parent_cls)
        return {
            "id": self.defect_id,
            "parent_index": self.parent_index,
            "parent_cls": self.parent_cls,
            "parent_label": parent_name,
            "type": self.defect_type,
            "severity": self.severity,
            "points": [
                [
                    round(max(0.0, min(float(width), x)) / max(1, width), 6),
                    round(max(0.0, min(float(height), y)) / max(1, height), 6),
                ]
                for x, y in self.points
            ],
            "note": self.note,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_json(item: dict, width: int, height: int) -> "DefectAnnotation | None":
        raw_points = item.get("points") or []
        points: list[tuple[float, float]] = []
        for raw_point in raw_points:
            if not isinstance(raw_point, (list, tuple)) or len(raw_point) != 2:
                continue
            try:
                points.append((float(raw_point[0]) * width, float(raw_point[1]) * height))
            except (TypeError, ValueError):
                continue
        if len(points) < 3:
            return None
        try:
            parent_index = int(item.get("parent_index", -1))
            parent_cls = int(item.get("parent_cls", 0))
        except (TypeError, ValueError):
            return None
        defect_type = str(item.get("type", "other"))
        severity = str(item.get("severity", "medium"))
        return DefectAnnotation(
            defect_id=str(item.get("id") or uuid.uuid4().hex[:12]),
            parent_index=parent_index,
            parent_cls=parent_cls,
            defect_type=defect_type if defect_type in DEFECT_TYPES else "other",
            severity=severity if severity in DEFECT_SEVERITIES else "medium",
            points=points,
            note=str(item.get("note") or ""),
            created_at=str(item.get("created_at") or ""),
        )


# ====================================================================
# 文件 IO
# ====================================================================


def cv_to_qimage(frame: np.ndarray) -> QImage:
    cv2 = get_cv2()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()


def load_image(path: Path) -> np.ndarray:
    cv2 = get_cv2()
    np = get_np()
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"图片读取失败：{path}")
    return img


def save_image(path: Path, img: np.ndarray) -> None:
    cv2 = get_cv2()
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".jpg", img)
    if not ok:
        raise RuntimeError(f"图片写入失败：{path}")
    data.tofile(str(path))


def safe_stem(text: str) -> str:
    keep = []
    for char in text:
        if char.isalnum() or char in "-_":
            keep.append(char)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "item"


def read_labels_file(path: Path, width: int, height: int) -> list[Annotation]:
    if not path.exists():
        return []
    items: list[Annotation] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            ann = Annotation.from_yolo_line(line, width, height)
            if ann is not None:
                items.append(ann)
    except OSError:
        pass
    return items


def write_labels_file(path: Path, annotations: list[Annotation], width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for ann in annotations:
        line = ann.to_yolo_line(width, height)
        if line is not None:
            lines.append(line)
    payload = "\n".join(lines) + ("\n" if lines else "")
    path.write_text(payload, encoding="utf-8")


def ensure_empty_label(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def write_data_yaml(output_root: Path, labels: list[str], task: str = "detect") -> None:
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        data = {
            "path": str(output_root).replace("\\", "/"),
            "train": "images/train",
            "val": "images/train",
            "task": task,
            "names": {idx: name for idx, name in enumerate(labels)},
            "cvds_defects": {
                "path": "defects/train",
                "version": DEFECT_META_VERSION,
                "types": {name: DEFECT_TYPE_LABELS[name] for name in DEFECT_TYPES},
                "severities": list(DEFECT_SEVERITIES),
            },
        }
        (output_root / "data.yaml").write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def read_data_yaml(output_root: Path) -> dict:
    data_yaml = output_root / "data.yaml"
    if not data_yaml.exists():
        return {}
    try:
        return yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    except OSError:
        return {}


def read_data_yaml_labels(output_root: Path) -> list[str]:
    data = read_data_yaml(output_root)
    names = data.get("names")
    if isinstance(names, list):
        return [str(name) for name in names]
    if isinstance(names, dict):
        try:
            return [str(names[key]) for key in sorted(names, key=lambda item: int(item))]
        except (TypeError, ValueError):
            return [str(v) for v in names.values()]
    return []


def label_path_for_image_path(image_path: Path, output_root: Path) -> Path:
    image_dir = (output_root / "images" / "train").resolve()
    resolved = image_path.resolve()
    try:
        resolved.relative_to(image_dir)
        stem = image_path.stem
    except ValueError:
        stem = safe_stem(image_path.stem)
    return output_root / "labels" / "train" / f"{stem}.txt"


def defect_path_for_image_path(image_path: Path, output_root: Path) -> Path:
    image_dir = (output_root / "images" / "train").resolve()
    resolved = image_path.resolve()
    try:
        resolved.relative_to(image_dir)
        stem = image_path.stem
    except ValueError:
        stem = safe_stem(image_path.stem)
    return output_root / "defects" / "train" / f"{stem}.json"


def read_defects_file(path: Path, width: int, height: int) -> list[DefectAnnotation]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore") or "{}")
    except (OSError, json.JSONDecodeError):
        return []
    raw_defects = payload.get("defects") if isinstance(payload, dict) else None
    if not isinstance(raw_defects, list):
        return []
    defects: list[DefectAnnotation] = []
    for item in raw_defects:
        if not isinstance(item, dict):
            continue
        defect = DefectAnnotation.from_json(item, width, height)
        if defect is not None:
            defects.append(defect)
    return defects


def write_defects_file(
    path: Path,
    defects: list[DefectAnnotation],
    width: int,
    height: int,
    image_path: Path,
    labels: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    valid_defects = [
        defect
        for defect in defects
        if defect.parent_index >= 0 and len(defect.points) >= 3
    ]
    if not valid_defects:
        if path.exists():
            path.unlink()
        return
    payload = {
        "version": DEFECT_META_VERSION,
        "image": image_path.name,
        "size": {"width": width, "height": height},
        "defects": [defect.to_json(width, height, labels) for defect in valid_defects],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def count_yolo_labels(path: Path) -> int:
    try:
        if not path.exists():
            return 0
        if path.stat().st_size == 0:
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())
    except OSError:
        return 0


# ====================================================================
# 图片列表模型
# ====================================================================


class ImageListModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.box_counts: list[int] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.paths)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self.paths):
            return None
        path = self.paths[index.row()]
        if role == Qt.DisplayRole:
            count = self.box_counts[index.row()]
            return f"{index.row() + 1}.[{count}] {path.name}"
        if role == Qt.ToolTipRole:
            return str(path)
        if role == Qt.UserRole:
            return int(self.box_counts[index.row()])
        return None

    def set_paths(self, paths: list[Path], box_counts: list[int] | None = None) -> None:
        self.beginResetModel()
        self.paths = list(paths)
        if box_counts is None or len(box_counts) != len(paths):
            self.box_counts = [0] * len(paths)
        else:
            self.box_counts = [int(c) for c in box_counts]
        self.endResetModel()

    def update_box_count(self, row: int, count: int) -> None:
        if 0 <= row < len(self.box_counts):
            self.box_counts[row] = int(count)
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [Qt.DisplayRole, Qt.UserRole])

    def update_path(self, row: int, path: Path) -> None:
        if 0 <= row < len(self.paths):
            self.paths[row] = path
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [Qt.DisplayRole, Qt.ToolTipRole])

    def box_count(self, row: int) -> int:
        if 0 <= row < len(self.box_counts):
            return self.box_counts[row]
        return 0

    def remove_row(self, row: int) -> None:
        if 0 <= row < len(self.paths):
            self.beginRemoveRows(QModelIndex(), row, row)
            self.paths.pop(row)
            self.box_counts.pop(row)
            self.endRemoveRows()


# ====================================================================
# 画布
# ====================================================================


class ImageCanvas(QWidget):
    annotations_changed = Signal()
    defects_changed = Signal()
    selection_changed = Signal(int)
    defect_selection_changed = Signal(int)
    class_changed = Signal(int)

    HANDLE = 7

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(760, 520)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.CrossCursor)

        self.pixmap: QPixmap | None = None
        self.image_size = (0, 0)
        self.annotations: list[Annotation] = []
        self.defects: list[DefectAnnotation] = []
        self.labels: list[str] = ["parcel"]
        self.current_cls = 0
        self.mode = "box"  # 'box' / 'polygon' / 'defect'
        self.selected = -1
        self.selected_defect = -1
        self.current_defect_type = "hole"
        self.current_defect_severity = "medium"
        self.current_defect_note = ""

        # 视图变换
        self.user_zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0

        # 矩形绘制
        self.drawing_box = False
        self.box_start: QPointF | None = None
        self.box_current: QPointF | None = None

        # 多边形绘制
        self.drawing_polygon = False
        self.polygon_points: list[tuple[float, float]] = []
        self.polygon_cursor: QPointF | None = None

        # 目标内部缺陷绘制
        self.drawing_defect = False
        self.defect_points: list[tuple[float, float]] = []
        self.defect_cursor: QPointF | None = None

        # 拖拽
        self.drag_mode: str | None = None  # 'move' / 'resize' / 'vertex' / 'pan'
        self.drag_start_img: QPointF | None = None
        self.drag_original_ann: Annotation | None = None
        self.drag_original_defects: list[DefectAnnotation] = []
        self.resize_handle: str | None = None
        self.vertex_index = -1
        self.drag_changed = False
        self.pan_last: QPoint | None = None

    # ---------- 视图变换 ----------

    def fit_scale(self) -> float:
        w, h = self.image_size
        if w <= 0 or h <= 0:
            return 1.0
        return min(self.width() / w, self.height() / h)

    def effective_scale(self) -> float:
        return self.fit_scale() * self.user_zoom

    def image_rect(self) -> QRectF:
        w, h = self.image_size
        if w <= 0 or h <= 0:
            return QRectF()
        scale = self.effective_scale()
        draw_w = w * scale
        draw_h = h * scale
        cx = self.width() / 2 + self.pan_x
        cy = self.height() / 2 + self.pan_y
        return QRectF(cx - draw_w / 2, cy - draw_h / 2, draw_w, draw_h)

    def widget_to_image(self, point, clamp: bool = True) -> QPointF | None:
        rect = self.image_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return None
        w, h = self.image_size
        x = (point.x() - rect.left()) / rect.width() * w
        y = (point.y() - rect.top()) / rect.height() * h
        if clamp:
            x = max(0.0, min(float(w), x))
            y = max(0.0, min(float(h), y))
        return QPointF(x, y)

    def image_to_widget(self, x: float, y: float) -> QPointF:
        rect = self.image_rect()
        w, h = self.image_size
        if w <= 0 or h <= 0:
            return QPointF(rect.left(), rect.top())
        return QPointF(rect.left() + x / w * rect.width(), rect.top() + y / h * rect.height())

    def image_to_widget_rect(self, ann: Annotation) -> QRectF:
        rect = self.image_rect()
        w, h = self.image_size
        if w <= 0 or h <= 0:
            return QRectF()
        b = ann.rect()
        return QRectF(
            rect.left() + b.left() / w * rect.width(),
            rect.top() + b.top() / h * rect.height(),
            b.width() / w * rect.width(),
            b.height() / h * rect.height(),
        )

    def reset_view(self) -> None:
        self.user_zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.update()

    def clamp_pan(self) -> None:
        if self.user_zoom <= 1.0 + 1e-6:
            self.pan_x = 0.0
            self.pan_y = 0.0
            return
        rect = self.image_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        max_pan_x = max(0.0, (rect.width() - self.width()) / 2 + self.width() * 0.25)
        max_pan_y = max(0.0, (rect.height() - self.height()) / 2 + self.height() * 0.25)
        self.pan_x = max(-max_pan_x, min(max_pan_x, self.pan_x))
        self.pan_y = max(-max_pan_y, min(max_pan_y, self.pan_y))

    # ---------- 公共接口 ----------

    def set_image(self, frame: np.ndarray | None) -> None:
        if frame is None:
            self.pixmap = None
            self.image_size = (0, 0)
        else:
            h, w = frame.shape[:2]
            self.image_size = (w, h)
            self.pixmap = QPixmap.fromImage(cv_to_qimage(frame))
        self._reset_interaction()
        self.selected = -1
        self.selected_defect = -1
        self.user_zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.update()

    def set_annotations(self, anns: list[Annotation]) -> None:
        self.annotations = list(anns)
        self.selected = -1
        self.selected_defect = -1
        self._prune_orphan_defects()
        self.update()

    def set_defects(self, defects: list[DefectAnnotation]) -> None:
        self.defects = [defect.copy() for defect in defects]
        self.selected_defect = -1
        self._prune_orphan_defects()
        self.update()

    def set_labels(self, labels: list[str]) -> None:
        self.labels = list(labels) if labels else ["parcel"]
        self.current_cls = max(0, min(self.current_cls, len(self.labels) - 1))
        self.update()

    def set_current_cls(self, cls: int) -> None:
        cls = max(0, min(int(cls), max(0, len(self.labels) - 1)))
        if cls != self.current_cls:
            self.current_cls = cls
            self.class_changed.emit(cls)
        self.update()

    def set_defect_meta(self, defect_type: str, severity: str, note: str = "") -> None:
        self.current_defect_type = defect_type if defect_type in DEFECT_TYPES else "other"
        self.current_defect_severity = severity if severity in DEFECT_SEVERITIES else "medium"
        self.current_defect_note = note.strip()

    def set_selected_class(self, cls: int) -> None:
        if 0 <= self.selected < len(self.annotations):
            self.annotations[self.selected].cls = int(cls)
            for defect in self.defects:
                if defect.parent_index == self.selected:
                    defect.parent_cls = int(cls)
            self.annotations_changed.emit()
            self.defects_changed.emit()
            self.update()

    def set_mode(self, mode: str) -> None:
        if mode in ("box", "polygon", "defect") and mode != self.mode:
            self.mode = mode
            self._reset_interaction()
            self.update()

    def select(self, idx: int) -> None:
        idx = idx if 0 <= idx < len(self.annotations) else -1
        if idx == -1 and self.selected_defect != -1:
            self.selected_defect = -1
            self.defect_selection_changed.emit(-1)
        if idx != self.selected:
            self.selected = idx
            if idx >= 0 and self.selected_defect != -1:
                self.selected_defect = -1
                self.defect_selection_changed.emit(-1)
            self.selection_changed.emit(idx)
            if idx >= 0:
                self.set_current_cls(self.annotations[idx].cls)
            self.update()

    def select_defect(self, idx: int) -> None:
        idx = idx if 0 <= idx < len(self.defects) else -1
        if idx != self.selected_defect:
            self.selected_defect = idx
            if idx >= 0:
                parent = self.defects[idx].parent_index
                if 0 <= parent < len(self.annotations):
                    self.selected = parent
                    self.selection_changed.emit(parent)
            self.defect_selection_changed.emit(idx)
            self.update()

    def delete_selected(self) -> None:
        if 0 <= self.selected_defect < len(self.defects):
            self.defects.pop(self.selected_defect)
            self.selected_defect = -1
            self.defect_selection_changed.emit(-1)
            self.defects_changed.emit()
            self.update()
            return
        if 0 <= self.selected < len(self.annotations):
            deleted_index = self.selected
            self.annotations.pop(deleted_index)
            self._remove_or_reindex_defects_for_deleted_parent(deleted_index)
            self.selected = -1
            self.selection_changed.emit(-1)
            self.annotations_changed.emit()
            self.defects_changed.emit()
            self.update()

    def rollback_current_action(self) -> bool:
        if self.drawing_defect:
            if self.defect_points:
                self.defect_points.pop()
            if not self.defect_points:
                self.drawing_defect = False
                self.defect_cursor = None
            else:
                x, y = self.defect_points[-1]
                self.defect_cursor = QPointF(x, y)
            self.update()
            return True
        if self.drawing_polygon:
            if self.polygon_points:
                self.polygon_points.pop()
            if not self.polygon_points:
                self.drawing_polygon = False
                self.polygon_cursor = None
            else:
                x, y = self.polygon_points[-1]
                self.polygon_cursor = QPointF(x, y)
            self.update()
            return True
        if self.drawing_box:
            self.drawing_box = False
            self.box_start = None
            self.box_current = None
            self.update()
            return True
        if self.drag_mode in ("move", "resize", "vertex") and self.drag_original_ann is not None:
            if 0 <= self.selected < len(self.annotations):
                self.annotations[self.selected] = self.drag_original_ann
                self.defects = [defect.copy() for defect in self.drag_original_defects]
                self.annotations_changed.emit()
                self.defects_changed.emit()
            self.drag_mode = None
            self.drag_start_img = None
            self.drag_original_ann = None
            self.drag_original_defects = []
            self.resize_handle = None
            self.vertex_index = -1
            self.drag_changed = False
            self.update()
            return True
        if self.drag_mode == "pan":
            self.drag_mode = None
            self.pan_last = None
            self.setCursor(Qt.CrossCursor)
            self.update()
            return True
        return False

    def clear_annotations(self) -> None:
        if self.annotations or self.defects:
            self.annotations = []
            self.defects = []
            self.selected = -1
            self.selected_defect = -1
            self.selection_changed.emit(-1)
            self.defect_selection_changed.emit(-1)
            self.annotations_changed.emit()
            self.defects_changed.emit()
            self.update()

    def _reset_interaction(self) -> None:
        self.drawing_box = False
        self.box_start = None
        self.box_current = None
        self.drawing_polygon = False
        self.polygon_points = []
        self.polygon_cursor = None
        self.drawing_defect = False
        self.defect_points = []
        self.defect_cursor = None
        self.drag_mode = None
        self.drag_start_img = None
        self.drag_original_ann = None
        self.drag_original_defects = []
        self.resize_handle = None
        self.vertex_index = -1
        self.drag_changed = False
        self.pan_last = None

    def _prune_orphan_defects(self) -> None:
        kept: list[DefectAnnotation] = []
        for defect in self.defects:
            if 0 <= defect.parent_index < len(self.annotations):
                defect.parent_cls = self.annotations[defect.parent_index].cls
                kept.append(defect)
        if len(kept) != len(self.defects):
            self.defects = kept
            self.selected_defect = -1

    def _remove_or_reindex_defects_for_deleted_parent(self, deleted_index: int) -> None:
        kept: list[DefectAnnotation] = []
        for defect in self.defects:
            if defect.parent_index == deleted_index:
                continue
            if defect.parent_index > deleted_index:
                defect = defect.copy()
                defect.parent_index -= 1
            if 0 <= defect.parent_index < len(self.annotations):
                defect.parent_cls = self.annotations[defect.parent_index].cls
                kept.append(defect)
        self.defects = kept
        self.selected_defect = -1

    def _shift_child_defects(self, parent_index: int, dx: float, dy: float) -> None:
        if not self.defects:
            return
        for defect in self.defects:
            if defect.parent_index != parent_index:
                continue
            defect.points = [self._clamp_xy(x + dx, y + dy) for x, y in defect.points]

    # ---------- 命中测试 ----------

    def hit_test(self, point: QPointF) -> int:
        candidates: list[tuple[float, int]] = []
        for idx in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[idx]
            if ann.contains(point.x(), point.y()):
                rect = ann.rect()
                area = max(1.0, rect.width() * rect.height())
                candidates.append((area, -idx))
        if not candidates:
            return -1
        candidates.sort()
        return -candidates[0][1]

    def hit_defect(self, point: QPointF) -> int:
        candidates: list[tuple[float, int]] = []
        for idx in range(len(self.defects) - 1, -1, -1):
            defect = self.defects[idx]
            if defect.contains(point.x(), point.y()):
                rect = defect.rect()
                area = max(1.0, rect.width() * rect.height())
                candidates.append((area, -idx))
        if not candidates:
            return -1
        candidates.sort()
        return -candidates[0][1]

    def selected_parent_for_defect(self) -> int:
        if 0 <= self.selected < len(self.annotations):
            return self.selected
        if 0 <= self.selected_defect < len(self.defects):
            parent = self.defects[self.selected_defect].parent_index
            if 0 <= parent < len(self.annotations):
                return parent
        return -1

    def point_inside_selected_parent(self, point: QPointF) -> bool:
        parent = self.selected_parent_for_defect()
        return parent >= 0 and self.annotations[parent].contains(point.x(), point.y())

    def hit_resize_handle(self, ann: Annotation, point: QPointF) -> str | None:
        if not ann.is_box:
            return None
        threshold = self._hit_threshold()
        rect = ann.rect()
        corners = {
            "tl": (rect.left(), rect.top()),
            "tr": (rect.right(), rect.top()),
            "bl": (rect.left(), rect.bottom()),
            "br": (rect.right(), rect.bottom()),
        }
        for name, (cx, cy) in corners.items():
            if abs(point.x() - cx) <= threshold and abs(point.y() - cy) <= threshold:
                return name
        return None

    def hit_vertex(self, ann: Annotation, point: QPointF) -> int:
        if not ann.is_polygon:
            return -1
        threshold = self._hit_threshold()
        for i, (vx, vy) in enumerate(ann.points):
            if abs(point.x() - vx) <= threshold and abs(point.y() - vy) <= threshold:
                return i
        return -1

    def _hit_threshold(self) -> float:
        w, h = self.image_size
        base = max(6.0, min(w, h) * 0.012) if (w and h) else 6.0
        scale = max(0.001, self.effective_scale())
        return base / scale

    # ---------- 变换辅助 ----------

    def _clamp_xy(self, x: float, y: float) -> tuple[float, float]:
        w, h = self.image_size
        return max(0.0, min(float(w), x)), max(0.0, min(float(h), y))

    def _moved_box(self, original: Annotation, start: QPointF, current: QPointF) -> Annotation:
        dx = current.x() - start.x()
        dy = current.y() - start.y()
        rect = original.rect()
        w, h = self.image_size
        max_left = max(0.0, float(w) - rect.width())
        max_top = max(0.0, float(h) - rect.height())
        new_left = max(0.0, min(max_left, rect.left() + dx))
        new_top = max(0.0, min(max_top, rect.top() + dy))
        return Annotation.from_box(
            original.cls,
            new_left,
            new_top,
            new_left + rect.width(),
            new_top + rect.height(),
            original.conf,
        )

    def _moved_polygon(self, original: Annotation, start: QPointF, current: QPointF) -> Annotation:
        dx = current.x() - start.x()
        dy = current.y() - start.y()
        pts: list[tuple[float, float]] = []
        for x, y in original.points:
            nx, ny = self._clamp_xy(x + dx, y + dy)
            pts.append((nx, ny))
        return Annotation(original.cls, "polygon", pts, original.conf)

    def _resized_box(self, original: Annotation, current: QPointF, handle: str) -> Annotation:
        x1, y1, x2, y2 = original.box_corners()
        left, right = sorted([x1, x2])
        top, bottom = sorted([y1, y2])
        x = current.x()
        y = current.y()
        if "l" in handle:
            left = x
        if "r" in handle:
            right = x
        if "t" in handle:
            top = y
        if "b" in handle:
            bottom = y
        left, right = sorted([left, right])
        top, bottom = sorted([top, bottom])
        left, top = self._clamp_xy(left, top)
        right, bottom = self._clamp_xy(right, bottom)
        return Annotation.from_box(original.cls, left, top, right, bottom, original.conf)

    # ---------- 滚轮缩放 ----------

    def wheelEvent(self, event):
        if not self.pixmap:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.2 if delta > 0 else 1 / 1.2
        new_zoom = max(1.0, min(20.0, self.user_zoom * factor))
        if abs(new_zoom - self.user_zoom) < 1e-6:
            return
        widget_pos = event.position()
        rect = self.image_rect()
        mx = widget_pos.x() - rect.center().x()
        my = widget_pos.y() - rect.center().y()
        ratio = new_zoom / self.user_zoom
        self.pan_x -= mx * (ratio - 1)
        self.pan_y -= my * (ratio - 1)
        self.user_zoom = new_zoom
        self.clamp_pan()
        self.update()

    # ---------- 鼠标事件 ----------

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing_defect and len(self.defect_points) >= 3:
            self._finish_defect()
            return
        if event.button() == Qt.LeftButton and self.drawing_polygon and len(self.polygon_points) >= 3:
            self._finish_polygon()
            return
        if event.button() in (Qt.MiddleButton, Qt.LeftButton):
            self.reset_view()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        # 拖拽视图：中键 或 Ctrl+左键
        if event.button() == Qt.MiddleButton or (
            event.button() == Qt.LeftButton and (event.modifiers() & Qt.ControlModifier)
        ):
            self.drag_mode = "pan"
            self.pan_last = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() == Qt.RightButton:
            if self.drawing_defect and len(self.defect_points) >= 3:
                self._finish_defect()
                return
            if self.drawing_polygon and len(self.polygon_points) >= 3:
                self._finish_polygon()
                return
            self._reset_interaction()
            self.update()
            return
        if event.button() != Qt.LeftButton:
            return
        image_point = self.widget_to_image(event.position())
        if image_point is None:
            return
        if self.drawing_defect:
            if self.point_inside_selected_parent(image_point):
                self.defect_points.append((image_point.x(), image_point.y()))
                self.defect_cursor = image_point
                self.update()
            return
        if self.drawing_polygon:
            self.polygon_points.append((image_point.x(), image_point.y()))
            self.polygon_cursor = image_point
            self.update()
            return
        if self.mode == "defect":
            defect_hit = self.hit_defect(image_point)
            if defect_hit >= 0:
                self.select_defect(defect_hit)
                return
            parent = self.selected_parent_for_defect()
            if parent >= 0 and self.annotations[parent].contains(image_point.x(), image_point.y()):
                self.drawing_defect = True
                self.defect_points = [(image_point.x(), image_point.y())]
                self.defect_cursor = image_point
                self.update()
                return
            hit = self.hit_test(image_point)
            if hit >= 0:
                self.select(hit)
                return
            return
        hit = self.hit_test(image_point)
        if hit >= 0:
            ann = self.annotations[hit]
            self.select(hit)
            self.drag_changed = False
            self.drag_original_ann = ann.copy()
            self.drag_original_defects = [defect.copy() for defect in self.defects]
            self.drag_start_img = image_point
            v = self.hit_vertex(ann, image_point)
            if v >= 0:
                self.drag_mode = "vertex"
                self.vertex_index = v
                return
            handle = self.hit_resize_handle(ann, image_point)
            if handle:
                self.drag_mode = "resize"
                self.resize_handle = handle
                return
            self.drag_mode = "move"
            return
        self.select(-1)
        if self.mode == "polygon":
            self.drawing_polygon = True
            self.polygon_points = [(image_point.x(), image_point.y())]
            self.polygon_cursor = image_point
            self.update()
            return
        self.drawing_box = True
        self.box_start = image_point
        self.box_current = image_point
        self.update()

    def mouseMoveEvent(self, event):
        if self.drag_mode == "pan" and self.pan_last is not None:
            pos = event.position().toPoint()
            self.pan_x += pos.x() - self.pan_last.x()
            self.pan_y += pos.y() - self.pan_last.y()
            self.pan_last = pos
            self.clamp_pan()
            self.update()
            return
        image_point = self.widget_to_image(event.position())
        if image_point is None:
            return
        if self.drawing_box:
            self.box_current = image_point
            self.update()
            return
        if self.drawing_defect:
            if self.point_inside_selected_parent(image_point):
                self.defect_cursor = image_point
            self.update()
            return
        if self.drawing_polygon:
            self.polygon_cursor = image_point
            self.update()
            return
        if (
            self.drag_mode in ("move", "resize", "vertex")
            and self.drag_original_ann is not None
            and self.drag_start_img is not None
            and 0 <= self.selected < len(self.annotations)
        ):
            ann = self.drag_original_ann
            if self.drag_mode == "move":
                if ann.is_box:
                    self.annotations[self.selected] = self._moved_box(ann, self.drag_start_img, image_point)
                else:
                    self.annotations[self.selected] = self._moved_polygon(ann, self.drag_start_img, image_point)
                dx = image_point.x() - self.drag_start_img.x()
                dy = image_point.y() - self.drag_start_img.y()
                self.defects = [defect.copy() for defect in self.drag_original_defects]
                self._shift_child_defects(self.selected, dx, dy)
            elif self.drag_mode == "resize" and self.resize_handle:
                self.annotations[self.selected] = self._resized_box(ann, image_point, self.resize_handle)
            elif self.drag_mode == "vertex" and 0 <= self.vertex_index < len(ann.points):
                pts = list(ann.points)
                pts[self.vertex_index] = self._clamp_xy(image_point.x(), image_point.y())
                self.annotations[self.selected] = Annotation(ann.cls, ann.kind, pts, ann.conf)
            self.drag_changed = True
            self.update()

    def mouseReleaseEvent(self, event):
        if self.drag_mode == "pan":
            self.drag_mode = None
            self.pan_last = None
            self.setCursor(Qt.CrossCursor)
            return
        if self.drag_mode in ("move", "resize", "vertex"):
            if self.drag_changed and 0 <= self.selected < len(self.annotations):
                ann = self.annotations[self.selected]
                if ann.is_box and (ann.rect().width() < 2 or ann.rect().height() < 2):
                    if self.drag_original_ann is not None:
                        self.annotations[self.selected] = self.drag_original_ann
                        self.defects = [defect.copy() for defect in self.drag_original_defects]
                else:
                    self.annotations_changed.emit()
                    self.defects_changed.emit()
            self.drag_mode = None
            self.drag_start_img = None
            self.drag_original_ann = None
            self.drag_original_defects = []
            self.resize_handle = None
            self.vertex_index = -1
            self.drag_changed = False
            self.update()
            return
        if self.drawing_box and self.box_start is not None and self.box_current is not None:
            self.drawing_box = False
            ann = Annotation.from_box(
                self.current_cls,
                self.box_start.x(),
                self.box_start.y(),
                self.box_current.x(),
                self.box_current.y(),
            )
            if ann.rect().width() >= 3 and ann.rect().height() >= 3:
                self.annotations.append(ann)
                self.select(len(self.annotations) - 1)
                self.annotations_changed.emit()
            self.box_start = None
            self.box_current = None
            self.update()

    def _finish_polygon(self) -> None:
        if not self.drawing_polygon or len(self.polygon_points) < 3:
            self.drawing_polygon = False
            self.polygon_points = []
            self.polygon_cursor = None
            self.update()
            return
        ann = Annotation.from_polygon(self.current_cls, self.polygon_points)
        self.annotations.append(ann)
        self.drawing_polygon = False
        self.polygon_points = []
        self.polygon_cursor = None
        self.select(len(self.annotations) - 1)
        self.annotations_changed.emit()
        self.update()

    def _finish_defect(self) -> None:
        parent_index = self.selected_parent_for_defect()
        if (
            not self.drawing_defect
            or parent_index < 0
            or parent_index >= len(self.annotations)
            or len(self.defect_points) < 3
        ):
            self.drawing_defect = False
            self.defect_points = []
            self.defect_cursor = None
            self.update()
            return
        parent = self.annotations[parent_index]
        if not all(parent.contains(x, y) for x, y in self.defect_points):
            self.drawing_defect = False
            self.defect_points = []
            self.defect_cursor = None
            self.update()
            return
        defect = DefectAnnotation.from_polygon(
            parent_index,
            parent,
            self.current_defect_type,
            self.current_defect_severity,
            self.defect_points,
            self.current_defect_note,
        )
        self.defects.append(defect)
        self.drawing_defect = False
        self.defect_points = []
        self.defect_cursor = None
        self.select_defect(len(self.defects) - 1)
        self.defects_changed.emit()
        self.update()

    # ---------- 键盘（画布内事件） ----------

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
            return
        if key == Qt.Key_Escape:
            self.rollback_current_action()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self.drawing_defect:
                self._finish_defect()
                return
            if self.drawing_polygon:
                self._finish_polygon()
                return
        if key == Qt.Key_Z and (event.modifiers() & Qt.ControlModifier):
            if self.drawing_defect and self.defect_points:
                self.defect_points.pop()
                if not self.defect_points:
                    self.drawing_defect = False
                self.update()
                return
            if self.drawing_polygon and self.polygon_points:
                self.polygon_points.pop()
                if not self.polygon_points:
                    self.drawing_polygon = False
                self.update()
                return
        super().keyPressEvent(event)

    # ---------- 绘制 ----------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor("#111827"))
        if not self.pixmap:
            painter.setPen(QColor("#d1d5db"))
            painter.drawText(self.rect(), Qt.AlignCenter, "请选择图片文件夹或抽帧后再加载")
            return
        rect = self.image_rect()
        painter.drawPixmap(rect, self.pixmap, QRectF(self.pixmap.rect()))

        for idx, ann in enumerate(self.annotations):
            color = SELECTED_COLOR if idx == self.selected else BOX_COLORS[ann.cls % len(BOX_COLORS)]
            pen = QPen(color, 3 if idx == self.selected else 2)
            painter.setPen(pen)
            if ann.is_box:
                painter.setBrush(Qt.NoBrush)
                bw_rect = self.image_to_widget_rect(ann)
                painter.drawRect(bw_rect)
                self._draw_label(painter, color, ann, bw_rect)
                if idx == self.selected:
                    self._draw_handles(painter, [bw_rect.topLeft(), bw_rect.topRight(), bw_rect.bottomLeft(), bw_rect.bottomRight()])
            else:
                pts = [self.image_to_widget(x, y) for x, y in ann.points]
                if not pts:
                    continue
                poly = QPolygonF(pts)
                fill = QColor(color)
                fill.setAlpha(60 if idx == self.selected else 36)
                painter.setBrush(fill)
                painter.drawPolygon(poly)
                bw_rect = self.image_to_widget_rect(ann)
                self._draw_label(painter, color, ann, bw_rect)
                if idx == self.selected:
                    self._draw_handles(painter, pts)

        for idx, defect in enumerate(self.defects):
            if len(defect.points) < 3 or not (0 <= defect.parent_index < len(self.annotations)):
                continue
            base_color = DEFECT_COLORS.get(defect.defect_type, DEFECT_COLORS["other"])
            color = SELECTED_COLOR if idx == self.selected_defect else base_color
            pts = [self.image_to_widget(x, y) for x, y in defect.points]
            poly = QPolygonF(pts)
            fill = QColor(color)
            fill.setAlpha(105 if idx == self.selected_defect else 78)
            painter.setPen(QPen(color, 3 if idx == self.selected_defect else 2, Qt.DashLine))
            painter.setBrush(fill)
            painter.drawPolygon(poly)
            if idx == self.selected_defect:
                self._draw_handles(painter, pts)
            self._draw_defect_label(painter, color, defect)

        if self.drawing_box and self.box_start and self.box_current:
            painter.setPen(QPen(QColor("#FFB000"), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            draft = Annotation.from_box(
                self.current_cls,
                self.box_start.x(),
                self.box_start.y(),
                self.box_current.x(),
                self.box_current.y(),
            )
            painter.drawRect(self.image_to_widget_rect(draft))

        if self.drawing_polygon and self.polygon_points:
            pts = [self.image_to_widget(x, y) for x, y in self.polygon_points]
            painter.setPen(QPen(QColor("#FFB000"), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i], pts[i + 1])
            if self.polygon_cursor is not None:
                cursor_widget = self.image_to_widget(self.polygon_cursor.x(), self.polygon_cursor.y())
                painter.drawLine(pts[-1], cursor_widget)
                if len(pts) >= 2:
                    painter.setPen(QPen(QColor("#FFB000"), 1, Qt.DotLine))
                    painter.drawLine(cursor_widget, pts[0])
            painter.setPen(QPen(QColor("#111827"), 1))
            painter.setBrush(QColor("#FFB000"))
            for p in pts:
                painter.drawRect(QRectF(p.x() - self.HANDLE / 2, p.y() - self.HANDLE / 2, self.HANDLE, self.HANDLE))

        if self.drawing_defect and self.defect_points:
            pts = [self.image_to_widget(x, y) for x, y in self.defect_points]
            color = DEFECT_COLORS.get(self.current_defect_type, DEFECT_COLORS["other"])
            painter.setPen(QPen(color, 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i], pts[i + 1])
            if self.defect_cursor is not None:
                cursor_widget = self.image_to_widget(self.defect_cursor.x(), self.defect_cursor.y())
                painter.drawLine(pts[-1], cursor_widget)
                if len(pts) >= 2:
                    painter.setPen(QPen(color, 1, Qt.DotLine))
                    painter.drawLine(cursor_widget, pts[0])
            painter.setPen(QPen(QColor("#111827"), 1))
            painter.setBrush(color)
            for p in pts:
                painter.drawEllipse(QRectF(p.x() - self.HANDLE / 2, p.y() - self.HANDLE / 2, self.HANDLE, self.HANDLE))

        if self.user_zoom > 1.001:
            painter.setPen(QColor("#9ca3af"))
            painter.drawText(QRectF(8, 8, 220, 20), Qt.AlignLeft, f"缩放 {self.user_zoom:.2f}×")
        if self.mode == "polygon":
            painter.setPen(QColor("#9ca3af"))
            painter.drawText(QRectF(8, self.height() - 24, 420, 20), Qt.AlignLeft,
                             "分割模式：左键加点，右键 / 回车 / 双击 完成，Ctrl+Z 撤销点")
        if self.mode == "defect":
            painter.setPen(QColor("#cbd5e1"))
            painter.drawText(
                QRectF(8, self.height() - 42, 720, 20),
                Qt.AlignLeft,
                "缺陷模式：先选中目标，再在目标内部左键画缺陷；右键 / 回车 / 双击完成",
            )
            parent = self.selected_parent_for_defect()
            if parent < 0:
                painter.setPen(QColor("#ffd166"))
                painter.drawText(QRectF(8, self.height() - 22, 520, 20), Qt.AlignLeft, "请选择一个目标实例后再标注缺陷")

    def _draw_label(self, painter: QPainter, color: QColor, ann: Annotation, widget_rect: QRectF) -> None:
        name = self.labels[ann.cls] if 0 <= ann.cls < len(self.labels) else str(ann.cls)
        suffix = "" if ann.conf is None else f" {ann.conf:.2f}"
        label = f"{name}{suffix}"
        text_width = max(70, len(label) * 9)
        painter.fillRect(QRectF(widget_rect.left(), max(0, widget_rect.top() - 22), text_width, 22), TEXT_BG)
        painter.setPen(color)
        painter.drawText(int(widget_rect.left() + 4), int(max(16, widget_rect.top() - 6)), label)

    def _draw_defect_label(self, painter: QPainter, color: QColor, defect: DefectAnnotation) -> None:
        rect = defect.rect()
        widget_rect = QRectF(
            self.image_to_widget(rect.left(), rect.top()),
            self.image_to_widget(rect.right(), rect.bottom()),
        ).normalized()
        type_text = DEFECT_TYPE_LABELS.get(defect.defect_type, defect.defect_type).split(" / ")[0]
        severity_text = DEFECT_SEVERITY_LABELS.get(defect.severity, defect.severity)
        label = f"{type_text} · {severity_text}"
        text_width = max(80, len(label) * 9)
        painter.fillRect(QRectF(widget_rect.left(), max(0, widget_rect.top() - 20), text_width, 20), TEXT_BG)
        painter.setPen(color)
        painter.drawText(int(widget_rect.left() + 4), int(max(15, widget_rect.top() - 5)), label)

    def _draw_handles(self, painter: QPainter, points) -> None:
        painter.setPen(QPen(QColor("#111827"), 1))
        painter.setBrush(SELECTED_COLOR)
        for p in points:
            painter.drawRect(QRectF(p.x() - self.HANDLE / 2, p.y() - self.HANDLE / 2, self.HANDLE, self.HANDLE))


# ====================================================================
# 后台任务
# ====================================================================


@dataclass
class AiParams:
    weights: str
    labels: list[str]
    selected_cls: int
    conf: float
    imgsz: int
    device: str
    output_root: Path
    task: str  # 'detect' or 'segment'


def predict_annotations(model, frame: np.ndarray, params: AiParams, model_names: dict[int, str]) -> list[Annotation]:
    result = model.predict(frame, conf=params.conf, imgsz=params.imgsz, device=params.device, verbose=False)[0]
    out: list[Annotation] = []
    if result.boxes is None:
        return out
    xyxy_arr = result.boxes.xyxy.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    cls_arr = result.boxes.cls.cpu().numpy()
    masks_xy = None
    if params.task == "segment":
        masks = getattr(result, "masks", None)
        if masks is not None:
            try:
                masks_xy = masks.xy  # list[np.ndarray (N,2)] in image coordinates
            except Exception:
                masks_xy = None
    label_map = {name: idx for idx, name in enumerate(params.labels)}
    for i, (xyxy, conf, cls) in enumerate(zip(xyxy_arr, confs, cls_arr)):
        model_cls = int(cls)
        model_name = model_names.get(model_cls, "")
        target_cls = label_map.get(model_name, params.selected_cls)
        x1, y1, x2, y2 = [float(v) for v in xyxy]
        if masks_xy is not None and i < len(masks_xy) and len(masks_xy[i]) >= 3:
            pts = [(float(x), float(y)) for x, y in masks_xy[i]]
            out.append(Annotation.from_polygon(target_cls, pts, float(conf)))
        else:
            out.append(Annotation.from_box(target_cls, x1, y1, x2, y2, float(conf)))
    return out


class ImageAutoLabelWorker(QObject):
    progress = Signal(int, int, str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, image_paths: list[Path], params: AiParams) -> None:
        super().__init__()
        self.image_paths = image_paths
        self.params = params

    def run(self) -> None:
        try:
            write_data_yaml(self.params.output_root, self.params.labels, task=self.params.task)
            image_dir = self.params.output_root / "images" / "train"
            label_dir = self.params.output_root / "labels" / "train"
            image_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            YOLO = get_yolo_cls()
            model = YOLO(self.params.weights)
            model_names = {int(k): str(v) for k, v in getattr(model, "names", {}).items()}
            total = 0
            for idx, src in enumerate(self.image_paths, 1):
                try:
                    frame = load_image(src)
                except Exception as exc:
                    self.progress.emit(idx, len(self.image_paths), f"跳过损坏 {src.name}：{exc}")
                    continue
                stem = safe_stem(src.stem)
                dst_img = image_dir / f"{stem}.jpg"
                save_image(dst_img, frame)
                anns = predict_annotations(model, frame, self.params, model_names)
                write_labels_file(label_dir / f"{stem}.txt", anns, frame.shape[1], frame.shape[0])
                total += len(anns)
                self.progress.emit(idx, len(self.image_paths), src.name)
            self.done.emit({"images": len(self.image_paths), "annotations": total, "output": str(self.params.output_root)})
        except Exception:
            self.failed.emit(traceback.format_exc())


class ImageScanWorker(QObject):
    progress = Signal(int, int, str)
    done = Signal(list, list, str)
    failed = Signal(str)

    def __init__(self, folder: Path, output_root: Path, create_empty_labels: bool = True) -> None:
        super().__init__()
        self.folder = folder
        self.output_root = output_root
        self.create_empty_labels = create_empty_labels

    def run(self) -> None:
        try:
            rows: list[tuple[str, int]] = []
            scanned = 0
            for root, _, files in os.walk(self.folder):
                for filename in files:
                    if Path(filename).suffix.lower() not in IMAGE_SUFFIXES:
                        continue
                    path = Path(root) / filename
                    label_path = label_path_for_image_path(path, self.output_root)
                    if self.create_empty_labels and not label_path.exists():
                        try:
                            ensure_empty_label(label_path)
                        except OSError:
                            pass
                    rows.append((str(path), count_yolo_labels(label_path)))
                    scanned += 1
                    if scanned % 2000 == 0:
                        self.progress.emit(scanned, 0, f"已扫描 {scanned} 张")
            rows.sort(key=lambda item: item[0].lower())
            self.done.emit([p for p, _ in rows], [c for _, c in rows], str(self.folder))
        except Exception:
            self.failed.emit(traceback.format_exc())


class DeleteEmptyLabelsWorker(QObject):
    progress = Signal(int, int, str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, image_paths: list[Path], output_root: Path) -> None:
        super().__init__()
        self.image_paths = image_paths
        self.output_root = output_root

    def run(self) -> None:
        try:
            image_dir = (self.output_root / "images" / "train").resolve()
            label_dir = self.output_root / "labels" / "train"
            defect_dir = self.output_root / "defects" / "train"
            deleted = 0
            checked = 0
            total = len(self.image_paths)
            for idx, image_path in enumerate(self.image_paths, 1):
                checked += 1
                try:
                    image_path.resolve().relative_to(image_dir)
                except ValueError:
                    continue
                label_path = label_dir / f"{image_path.stem}.txt"
                if count_yolo_labels(label_path) == 0:
                    try:
                        image_path.unlink(missing_ok=True)
                        label_path.unlink(missing_ok=True)
                        (defect_dir / f"{image_path.stem}.json").unlink(missing_ok=True)
                        deleted += 1
                    except OSError:
                        pass
                if idx % 2000 == 0:
                    self.progress.emit(idx, total, f"已检查 {idx}，删除 {deleted}")
            self.done.emit({"checked": checked, "deleted": deleted, "output": str(self.output_root)})
        except Exception:
            self.failed.emit(traceback.format_exc())


class VideoExtractWorker(QObject):
    progress = Signal(int, int, str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        video_paths: list[Path],
        frame_step: int,
        max_frames: int,
        output_root: Path,
        labels: list[str],
        params: AiParams | None,
        task: str,
    ) -> None:
        super().__init__()
        self.video_paths = video_paths
        self.frame_step = max(1, frame_step)
        self.max_frames = max_frames
        self.output_root = output_root
        self.labels = labels
        self.params = params
        self.task = task

    def run(self) -> None:
        try:
            cv2 = get_cv2()
            write_data_yaml(self.output_root, self.labels, task=self.task)
            image_dir = self.output_root / "images" / "train"
            label_dir = self.output_root / "labels" / "train"
            image_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            model = None
            model_names: dict[int, str] = {}
            if self.params is not None:
                YOLO = get_yolo_cls()
                model = YOLO(self.params.weights)
                model_names = {int(k): str(v) for k, v in getattr(model, "names", {}).items()}

            total_frames = 0
            total_anns = 0
            total_jobs = len(self.video_paths)
            for video_idx, video in enumerate(self.video_paths, 1):
                cap = cv2.VideoCapture(str(video))
                if not cap.isOpened():
                    self.progress.emit(video_idx, total_jobs, f"跳过：{video.name}")
                    continue
                frame_idx = 0
                saved = 0
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    if frame_idx % self.frame_step == 0:
                        stem = f"{safe_stem(video.stem)}_{frame_idx:06d}"
                        save_image(image_dir / f"{stem}.jpg", frame)
                        if model is not None and self.params is not None:
                            anns = predict_annotations(model, frame, self.params, model_names)
                        else:
                            anns = []
                        write_labels_file(label_dir / f"{stem}.txt", anns, frame.shape[1], frame.shape[0])
                        total_anns += len(anns)
                        total_frames += 1
                        saved += 1
                        if self.max_frames > 0 and saved >= self.max_frames:
                            break
                    frame_idx += 1
                cap.release()
                self.progress.emit(video_idx, total_jobs, video.name)
            self.done.emit({"frames": total_frames, "annotations": total_anns, "output": str(self.output_root)})
        except Exception:
            self.failed.emit(traceback.format_exc())


# ====================================================================
# 主窗口
# ====================================================================


def add_path_row(layout: QGridLayout, row: int, label: str, edit: QLineEdit, callback) -> None:
    button = QPushButton("选择")
    button.setMinimumWidth(58)
    button.clicked.connect(callback)
    layout.addWidget(QLabel(label), row, 0)
    layout.addWidget(edit, row, 1)
    layout.addWidget(button, row, 2)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CVDS AI 辅助 YOLO 标注工具 v2")
        self.settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        # 状态
        self.image_paths: list[Path] = []
        self.current_index = -1
        self.current_frame: np.ndarray | None = None
        self.worker_thread: QThread | None = None
        self.worker: QObject | None = None
        self.after_worker_callback = None
        self.empty_filter_enabled = False
        self.full_paths: list[Path] = []
        self.full_box_counts: list[int] = []
        self._silent_class_change = False
        self._silent_labels_change = False
        self._restored_initial_index = False

        # 标签编辑 debounce
        self._label_debounce = QTimer(self)
        self._label_debounce.setSingleShot(True)
        self._label_debounce.setInterval(400)
        self._label_debounce.timeout.connect(lambda: self.reload_labels(write_yaml=True))

        # 控件
        self.canvas = ImageCanvas()
        self.image_model = ImageListModel()
        self.image_list = QListView()
        self.image_list.setModel(self.image_model)
        self.image_list.setUniformItemSizes(True)
        self.image_list.setAlternatingRowColors(True)
        self.image_list.setSelectionMode(QListView.SingleSelection)
        self.image_list.selectionModel().currentChanged.connect(self.on_image_current_changed)
        self.canvas.annotations_changed.connect(self.on_annotations_changed)
        self.canvas.defects_changed.connect(self.on_defects_changed)
        self.canvas.selection_changed.connect(self.on_selection_changed)
        self.canvas.defect_selection_changed.connect(self.on_defect_selection_changed)
        self.canvas.class_changed.connect(self.on_canvas_class_changed)

        # 布局
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        left_content = self.build_left_panel()
        self.left_shell = QScrollArea()
        self.left_shell.setWidgetResizable(True)
        self.left_shell.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.left_shell.setWidget(left_content)
        self.left_shell.setMinimumWidth(560)
        self.left_shell.setMaximumWidth(700)
        left_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_policy.setHorizontalStretch(0)
        self.left_shell.setSizePolicy(left_policy)
        self.right_shell = self.build_right_panel()
        self.right_shell.setMinimumWidth(640)
        right_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_policy.setHorizontalStretch(1)
        self.right_shell.setSizePolicy(right_policy)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.left_shell)
        self.splitter.addWidget(self.right_shell)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter)

        self.statusBar().showMessage(self.device_text())
        self.setup_shortcuts()
        self.restore_settings()
        self.reload_labels(write_yaml=False)
        self.update_defect_meta()

    # -------------------- UI 构建 --------------------

    def build_left_panel(self) -> QWidget:
        page = QWidget()
        page.setObjectName("LeftPanel")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 路径
        io_box = QGroupBox("路径")
        io_form = QGridLayout(io_box)
        self.weights_edit = QLineEdit(str(DEFAULT_WEIGHTS))
        self.image_folder_edit = QLineEdit(str(DEFAULT_IMAGE_FOLDER if DEFAULT_IMAGE_FOLDER.exists() else ROOT))
        self.video_folder_edit = QLineEdit(str(DEFAULT_VIDEO_FOLDER))
        self.output_edit = QLineEdit(str(DEFAULT_OUTPUT))
        add_path_row(io_form, 0, "模型权重", self.weights_edit, self.pick_weights)
        add_path_row(io_form, 1, "图片文件夹", self.image_folder_edit, self.pick_image_folder)
        add_path_row(io_form, 2, "视频文件夹", self.video_folder_edit, self.pick_video_folder)
        add_path_row(io_form, 3, "输出YOLO目录", self.output_edit, self.pick_output)
        self.load_yolo_btn = QPushButton("读取YOLO目录")
        self.load_yolo_btn.clicked.connect(self.load_yolo_folder_from_output)
        io_form.addWidget(self.load_yolo_btn, 4, 1, 1, 2)

        # 标签 + 模式
        label_box = QGroupBox("标签")
        label_layout = QVBoxLayout(label_box)
        self.labels_edit = QPlainTextEdit("parcel")
        self.labels_edit.setMinimumHeight(86)
        self.labels_edit.textChanged.connect(self._on_labels_text_changed)
        mode_row = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["检测框 (detect)", "目标分割 (segment)", "目标内缺陷"])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_row.addWidget(QLabel("模式"))
        mode_row.addWidget(self.mode_combo, 1)
        class_row = QHBoxLayout()
        self.class_combo = QComboBox()
        self.class_combo.currentIndexChanged.connect(self.on_class_combo_changed)
        class_row.addWidget(QLabel("当前类别"))
        class_row.addWidget(self.class_combo, 1)
        label_layout.addWidget(self.labels_edit)
        label_layout.addLayout(mode_row)
        label_layout.addLayout(class_row)
        hint = QLabel("0-9 切换当前类别 ；Shift+0-9 修改选中标注类别")
        hint.setObjectName("HintLabel")
        hint.setStyleSheet("color:#9ca3af; font-size:11px;")
        label_layout.addWidget(hint)

        # 缺陷层：参考 CVAT/Label Studio 的对象属性思路，独立绑定到选中的目标实例。
        defect_box = QGroupBox("目标内缺陷")
        defect_form = QFormLayout(defect_box)
        self.defect_type_combo = QComboBox()
        for defect_type in DEFECT_TYPES:
            self.defect_type_combo.addItem(DEFECT_TYPE_LABELS[defect_type], defect_type)
        self.defect_severity_combo = QComboBox()
        for severity in DEFECT_SEVERITIES:
            self.defect_severity_combo.addItem(DEFECT_SEVERITY_LABELS[severity], severity)
        self.defect_note_edit = QLineEdit()
        self.defect_note_edit.setPlaceholderText("可选备注，例如贯穿/疑似/边缘缺口")
        self.defect_type_combo.currentIndexChanged.connect(self.update_defect_meta)
        self.defect_severity_combo.currentIndexChanged.connect(self.update_defect_meta)
        self.defect_note_edit.textChanged.connect(self.update_defect_meta)
        defect_form.addRow("类型", self.defect_type_combo)
        defect_form.addRow("程度", self.defect_severity_combo)
        defect_form.addRow("备注", self.defect_note_edit)

        # AI 参数
        ai_box = QGroupBox("AI 标注参数")
        ai_form = QFormLayout(ai_box)
        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.01, 0.99)
        self.conf_spin.setSingleStep(0.05)
        self.conf_spin.setValue(0.25)
        self.imgsz_spin = QSpinBox()
        self.imgsz_spin.setRange(160, 1536)
        self.imgsz_spin.setSingleStep(32)
        self.imgsz_spin.setValue(960)
        self.device_combo = QComboBox()
        if detect_cuda_device_name():
            self.device_combo.addItems(["0", "cpu"])
        else:
            self.device_combo.addItems(["cpu"])
        ai_form.addRow("置信度", self.conf_spin)
        ai_form.addRow("输入尺寸", self.imgsz_spin)
        ai_form.addRow("设备", self.device_combo)

        # 视频抽帧
        video_box = QGroupBox("视频抽帧")
        video_form = QFormLayout(video_box)
        self.frame_step_spin = QSpinBox()
        self.frame_step_spin.setRange(1, 10000)
        self.frame_step_spin.setValue(30)
        self.max_frames_spin = QSpinBox()
        self.max_frames_spin.setRange(0, 100000)
        self.max_frames_spin.setValue(120)
        video_form.addRow("每N帧保存", self.frame_step_spin)
        video_form.addRow("每视频最多", self.max_frames_spin)

        # 主要操作
        op_box = QGroupBox("主要操作")
        op_grid = QGridLayout(op_box)
        self.scan_btn = QPushButton("加载图片")
        self.scan_btn.clicked.connect(self.scan_images)
        self.ai_btn = QPushButton("AI批量标注图片")
        self.ai_btn.clicked.connect(self.ai_label_images)
        self.extract_btn = QPushButton("视频批量抽帧")
        self.extract_btn.clicked.connect(lambda: self.extract_videos(False))
        self.extract_ai_btn = QPushButton("抽帧并AI标注")
        self.extract_ai_btn.clicked.connect(lambda: self.extract_videos(True))
        self.save_btn = QPushButton("保存当前 (Ctrl+S)")
        self.save_btn.clicked.connect(self.save_current)
        self.delete_btn = QPushButton("删除选中框 (Del)")
        self.delete_btn.clicked.connect(self.delete_selected_box)
        op_grid.addWidget(self.scan_btn, 0, 0)
        op_grid.addWidget(self.ai_btn, 0, 1)
        op_grid.addWidget(self.extract_btn, 1, 0)
        op_grid.addWidget(self.extract_ai_btn, 1, 1)
        op_grid.addWidget(self.save_btn, 2, 0)
        op_grid.addWidget(self.delete_btn, 2, 1)

        # 手工辅助
        manual_box = QGroupBox("手工辅助")
        manual_grid = QGridLayout(manual_box)
        self.save_next_btn = QPushButton("保存并下一张 (Ctrl+Shift+S)")
        self.save_next_btn.clicked.connect(self.save_and_next)
        self.clear_boxes_btn = QPushButton("清空当前框 (C)")
        self.clear_boxes_btn.clicked.connect(self.clear_current_boxes)
        self.copy_prev_btn = QPushButton("复制上一张框 (V)")
        self.copy_prev_btn.clicked.connect(self.copy_previous_boxes)
        self.next_empty_btn = QPushButton("下一个空标注 (Ctrl+E)")
        self.next_empty_btn.clicked.connect(self.goto_next_empty_label)
        self.delete_frame_btn = QPushButton("删除当前帧 (Ctrl+D)")
        self.delete_frame_btn.clicked.connect(self.delete_current_frame)
        self.delete_empty_btn = QPushButton("批量删除空标签帧")
        self.delete_empty_btn.clicked.connect(self.delete_empty_label_frames)
        manual_grid.addWidget(self.save_next_btn, 0, 0)
        manual_grid.addWidget(self.clear_boxes_btn, 0, 1)
        manual_grid.addWidget(self.copy_prev_btn, 1, 0)
        manual_grid.addWidget(self.next_empty_btn, 1, 1)
        manual_grid.addWidget(self.delete_frame_btn, 2, 0)
        manual_grid.addWidget(self.delete_empty_btn, 2, 1)

        # 过滤
        filter_box = QGroupBox("视图过滤")
        filter_layout = QHBoxLayout(filter_box)
        self.only_empty_check = QCheckBox("只看负样本 (0 框图片)")
        self.only_empty_check.toggled.connect(self.on_empty_filter_toggled)
        filter_layout.addWidget(self.only_empty_check)
        filter_layout.addStretch(1)

        # 跳转
        jump_box = QGroupBox("快速跳转")
        jump_layout = QHBoxLayout(jump_box)
        self.jump_edit = QLineEdit()
        self.jump_edit.setPlaceholderText("行号或文件名片段，回车跳转 (Ctrl+G)")
        self.jump_edit.returnPressed.connect(self.do_jump)
        jump_btn = QPushButton("跳转")
        jump_btn.clicked.connect(self.do_jump)
        jump_layout.addWidget(self.jump_edit, 1)
        jump_layout.addWidget(jump_btn)

        # 进度 + 日志
        self.progress = QProgressBar()
        self.progress.hide()
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(96)
        self.log.setMaximumHeight(150)

        layout.addWidget(io_box)
        layout.addWidget(label_box)
        layout.addWidget(defect_box)
        layout.addWidget(ai_box)
        layout.addWidget(video_box)
        layout.addWidget(op_box)
        layout.addWidget(manual_box)
        layout.addWidget(filter_box)
        layout.addWidget(jump_box)
        layout.addWidget(self.progress)
        layout.addWidget(QLabel("图片列表"))
        layout.addWidget(self.image_list, 1)
        layout.addWidget(self.log)
        return page

    def build_right_panel(self) -> QWidget:
        page = QWidget()
        page.setObjectName("RightPanel")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(8)
        nav = QHBoxLayout()
        prev10_btn = QPushButton("⏪ -10")
        prev_btn = QPushButton("◀ 上一张 (A)")
        next_btn = QPushButton("下一张 (D) ▶")
        next10_btn = QPushButton("+10 ⏩")
        prev10_btn.clicked.connect(lambda: self.step_image(-10))
        prev_btn.clicked.connect(lambda: self.step_image(-1))
        next_btn.clicked.connect(lambda: self.step_image(1))
        next10_btn.clicked.connect(lambda: self.step_image(10))
        reset_view_btn = QPushButton("重置视图 (R)")
        reset_view_btn.clicked.connect(self.canvas.reset_view)
        self.info_label = QLabel("未加载")
        self.info_label.setObjectName("InfoLabel")
        self.info_label.setStyleSheet("padding:4px 8px;")
        nav.addWidget(prev10_btn)
        nav.addWidget(prev_btn)
        nav.addWidget(next_btn)
        nav.addWidget(next10_btn)
        nav.addWidget(reset_view_btn)
        nav.addWidget(self.info_label, 1)

        canvas_hint = QLabel(
            "左键：画框/选中/绘制缺陷  Esc：撤回当前点  右键/回车/双击：完成多边形  中键/Ctrl+左键：拖拽视图"
        )
        canvas_hint.setObjectName("HintLabel")
        canvas_hint.setStyleSheet("color:#9ca3af; font-size:11px;")

        self.box_table = QTableWidget(0, 6)
        self.box_table.setHorizontalHeaderLabels(["类型", "类别", "x/参数1", "y/参数2", "x2/宽度", "y2/高度"])
        self.box_table.cellClicked.connect(self.select_box_from_table)
        self.box_table.setMaximumHeight(150)

        self.defect_table = QTableWidget(0, 6)
        self.defect_table.setHorizontalHeaderLabels(["目标#", "缺陷", "程度", "点数", "备注", "ID"])
        self.defect_table.cellClicked.connect(self.select_defect_from_table)
        self.defect_table.setMaximumHeight(140)

        layout.addLayout(nav)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(canvas_hint)
        layout.addWidget(QLabel("当前图片目标标注"))
        layout.addWidget(self.box_table)
        layout.addWidget(QLabel("目标内缺陷标注"))
        layout.addWidget(self.defect_table)
        return page

    def device_text(self) -> str:
        device_name = detect_cuda_device_name()
        if device_name:
            return f"CUDA 可用：{device_name}"
        return "CUDA 未检测到：当前环境将使用 CPU"

    # -------------------- 快捷键 --------------------

    def _guard(self, callback):
        """包装回调：当焦点在文本输入控件时不响应。"""
        def runner():
            widget = QApplication.focusWidget()
            if isinstance(widget, (QLineEdit, QPlainTextEdit)):
                return
            callback()
        return runner

    def setup_shortcuts(self) -> None:
        self.shortcuts: list[QShortcut] = []
        always_bindings = [
            ("Ctrl+S", self.save_current),
            ("Ctrl+Shift+S", self.save_and_next),
            ("Ctrl+Left", lambda: self.step_image(-1)),
            ("Ctrl+Right", lambda: self.step_image(1)),
            ("Ctrl+E", self.goto_next_empty_label),
            ("Ctrl+D", self.delete_current_frame),
            ("Ctrl+G", self.focus_jump_box),
        ]
        guarded_bindings = [
            ("A", lambda: self.step_image(-1)),
            ("D", lambda: self.step_image(1)),
            ("Esc", self.canvas.rollback_current_action),
            ("Alt+B", lambda: self.mode_combo.setCurrentIndex(0)),
            ("Alt+P", lambda: self.mode_combo.setCurrentIndex(1)),
            ("Alt+X", lambda: self.mode_combo.setCurrentIndex(2)),
            ("PgUp", lambda: self.step_image(-10)),
            ("PgDown", lambda: self.step_image(10)),
            ("Home", lambda: self.goto_index(0)),
            ("End", lambda: self.goto_index(len(self.image_paths) - 1)),
            ("C", self.clear_current_boxes),
            ("V", self.copy_previous_boxes),
            ("R", self.canvas.reset_view),
            ("Q", lambda: self.shift_class(-1)),
            ("E", lambda: self.shift_class(1)),
            ("Space", self.save_current),
            ("Delete", self.delete_selected_box),
        ]
        for seq, cb in always_bindings:
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(cb)
            self.shortcuts.append(sc)
        for seq, cb in guarded_bindings:
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(self._guard(cb))
            self.shortcuts.append(sc)
        for i in range(10):
            sc1 = QShortcut(QKeySequence(str(i)), self)
            sc1.activated.connect(self._guard(lambda i=i: self.pick_class(i, apply_to_selected=False)))
            self.shortcuts.append(sc1)
            sc2 = QShortcut(QKeySequence(f"Shift+{i}"), self)
            sc2.activated.connect(self._guard(lambda i=i: self.pick_class(i, apply_to_selected=True)))
            self.shortcuts.append(sc2)

    def pick_class(self, idx: int, apply_to_selected: bool) -> None:
        labels = self.labels()
        if idx >= len(labels):
            return
        if apply_to_selected:
            self.canvas.set_selected_class(idx)
        self._silent_class_change = True
        self.class_combo.setCurrentIndex(idx)
        self._silent_class_change = False
        self.canvas.set_current_cls(idx)
        self.refresh_box_table()

    def shift_class(self, step: int) -> None:
        labels = self.labels()
        if not labels:
            return
        target = (self.class_combo.currentIndex() + step) % len(labels)
        self.pick_class(target, apply_to_selected=False)

    def focus_jump_box(self) -> None:
        self.jump_edit.setFocus()
        self.jump_edit.selectAll()

    # -------------------- 标签/模式 --------------------

    def _on_labels_text_changed(self) -> None:
        if self._silent_labels_change:
            return
        # 立刻刷新内存中的类别列表（不写盘），写盘 debounce
        self.reload_labels(write_yaml=False)
        self._label_debounce.start()

    def labels(self) -> list[str]:
        labels = [line.strip() for line in self.labels_edit.toPlainText().splitlines() if line.strip()]
        return labels or ["parcel"]

    def reload_labels(self, write_yaml: bool = True) -> None:
        labels = self.labels()
        current = self.class_combo.currentIndex()
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        self.class_combo.addItems(labels)
        new_index = max(0, min(current if current >= 0 else 0, len(labels) - 1))
        self.class_combo.setCurrentIndex(new_index)
        self.class_combo.blockSignals(False)
        self.canvas.set_labels(labels)
        self.canvas.set_current_cls(new_index)
        self.refresh_box_table()
        if write_yaml:
            write_data_yaml(self.output_root(), labels, task=self.current_task())

    def update_defect_meta(self) -> None:
        defect_type = self.defect_type_combo.currentData() or "other"
        severity = self.defect_severity_combo.currentData() or "medium"
        note = self.defect_note_edit.text()
        self.canvas.set_defect_meta(defect_type, severity, note)
        idx = self.canvas.selected_defect
        if 0 <= idx < len(self.canvas.defects):
            defect = self.canvas.defects[idx]
            defect.defect_type = defect_type if defect_type in DEFECT_TYPES else "other"
            defect.severity = severity if severity in DEFECT_SEVERITIES else "medium"
            defect.note = note.strip()
            self.canvas.defects_changed.emit()
            self.canvas.update()

    def current_task(self) -> str:
        return "detect" if self.mode_combo.currentIndex() == 0 else "segment"

    def on_mode_changed(self, idx: int) -> None:
        if idx == 0:
            mode = "box"
        elif idx == 1:
            mode = "polygon"
        else:
            mode = "defect"
        self.canvas.set_mode(mode)
        write_data_yaml(self.output_root(), self.labels(), task=self.current_task())

    def on_class_combo_changed(self, idx: int) -> None:
        if self._silent_class_change:
            return
        self.canvas.set_current_cls(idx)
        # 仅切换默认类别，不自动改变选中标注（避免误触）
        self.refresh_box_table()

    def on_canvas_class_changed(self, idx: int) -> None:
        if 0 <= idx < self.class_combo.count() and self.class_combo.currentIndex() != idx:
            self._silent_class_change = True
            self.class_combo.setCurrentIndex(idx)
            self._silent_class_change = False

    def set_labels_from_yolo_folder(self, output_root: Path) -> None:
        data = read_data_yaml(output_root)
        names = read_data_yaml_labels(output_root)
        if names:
            self._silent_labels_change = True
            self.labels_edit.setPlainText("\n".join(names))
            self._silent_labels_change = False
        task = data.get("task")
        if task == "segment":
            self.mode_combo.setCurrentIndex(1)
        elif task == "detect":
            self.mode_combo.setCurrentIndex(0)
        self.reload_labels(write_yaml=False)

    # -------------------- 路径选择 --------------------

    def pick_weights(self) -> None:
        existing = Path(self.weights_edit.text())
        start = str(existing.parent if existing.exists() else (ROOT / "weights"))
        path, _ = QFileDialog.getOpenFileName(self, "选择模型权重", start, "PyTorch (*.pt)")
        if path:
            self.weights_edit.setText(path)

    def pick_image_folder(self) -> None:
        start = self.image_folder_edit.text() or str(ROOT)
        path = QFileDialog.getExistingDirectory(self, "选择图片文件夹", start)
        if path:
            self.image_folder_edit.setText(path)

    def pick_video_folder(self) -> None:
        start = self.video_folder_edit.text() or str(ROOT)
        path = QFileDialog.getExistingDirectory(self, "选择视频文件夹", start)
        if path:
            self.video_folder_edit.setText(path)

    def pick_output(self) -> None:
        start = self.output_edit.text() or str(ROOT / "datasets")
        path = QFileDialog.getExistingDirectory(self, "选择YOLO输出目录", start)
        if path:
            self.output_edit.setText(path)
            self.set_labels_from_yolo_folder(Path(path))

    def load_yolo_folder_from_output(self) -> None:
        output_root = self.output_root()
        image_dir = output_root / "images" / "train"
        if not image_dir.exists():
            QMessageBox.warning(self, "目录不完整", f"没有找到 YOLO 图片目录：{image_dir}")
            return
        self.set_labels_from_yolo_folder(output_root)
        self.image_folder_edit.setText(str(image_dir))
        self.start_image_scan(image_dir)

    def output_root(self) -> Path:
        text = self.output_edit.text().strip()
        return Path(text or str(DEFAULT_OUTPUT)).resolve()

    def label_path_for_image(self, image_path: Path) -> Path:
        return label_path_for_image_path(image_path, self.output_root())

    def defect_path_for_image(self, image_path: Path) -> Path:
        return defect_path_for_image_path(image_path, self.output_root())

    def is_output_image_path(self, image_path: Path) -> bool:
        image_dir = (self.output_root() / "images" / "train").resolve()
        try:
            image_path.resolve().relative_to(image_dir)
            return True
        except ValueError:
            return False

    def output_image_path(self, image_path: Path) -> Path:
        if self.is_output_image_path(image_path):
            return image_path
        return self.output_root() / "images" / "train" / f"{safe_stem(image_path.stem)}.jpg"

    # -------------------- 扫描 --------------------

    def scan_images(self) -> None:
        folder = Path(self.image_folder_edit.text())
        self.start_image_scan(folder)

    def scan_output_images(self) -> None:
        folder = self.output_root() / "images" / "train"
        self.image_folder_edit.setText(str(folder))
        self.scan_images()

    def start_image_scan(self, folder: Path) -> None:
        if self.worker_thread is not None:
            QMessageBox.information(self, "任务运行中", "请等待当前任务完成")
            return
        if not folder.exists():
            QMessageBox.warning(self, "目录不存在", f"图片文件夹不存在：{folder}")
            return
        self.set_controls_enabled(False)
        self.progress.show()
        self.progress.setRange(0, 0)
        self.progress.setValue(0)
        self.append_log(f"扫描图片：{folder}")
        self.worker_thread = QThread()
        self.worker = ImageScanWorker(folder, self.output_root(), create_empty_labels=True)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.worker_progress)
        self.worker.done.connect(self.image_scan_done)
        self.worker.failed.connect(self.worker_failed)
        self.worker.done.connect(lambda *_: self.worker_thread.quit())
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.cleanup_worker)
        self.worker_thread.start()

    def image_scan_done(self, paths: list[str], box_counts: list[int], folder: str) -> None:
        self.full_paths = [Path(p) for p in paths]
        self.full_box_counts = list(box_counts)
        self.apply_image_list()
        self.append_log(f"加载 {len(self.full_paths)} 张图片：{folder}")

    def apply_image_list(self) -> None:
        if self.empty_filter_enabled:
            pairs = [(p, c) for p, c in zip(self.full_paths, self.full_box_counts) if c == 0]
        else:
            pairs = list(zip(self.full_paths, self.full_box_counts))
        self.image_paths = [p for p, _ in pairs]
        counts = [c for _, c in pairs]
        self.current_index = -1
        self.current_frame = None
        self.canvas.set_image(None)
        self.canvas.set_annotations([])
        self.image_model.set_paths(self.image_paths, counts)
        if self.image_paths:
            target = 0
            if not self._restored_initial_index:
                last_idx = self.settings.value("ui/last_image_index", 0)
                try:
                    last_idx = int(last_idx)
                except (TypeError, ValueError):
                    last_idx = 0
                if 0 <= last_idx < len(self.image_paths):
                    target = last_idx
                self._restored_initial_index = True
            idx = self.image_model.index(target, 0)
            self.image_list.setCurrentIndex(idx)
            self.image_list.scrollTo(idx)
        else:
            self.info_label.setText("未加载")
            self.refresh_box_table()

    def on_empty_filter_toggled(self, checked: bool) -> None:
        if self.worker_thread is not None:
            QMessageBox.information(self, "任务运行中", "请等待任务完成后再切换过滤")
            self.only_empty_check.blockSignals(True)
            self.only_empty_check.setChecked(not checked)
            self.only_empty_check.blockSignals(False)
            return
        self.save_current(silent=True)
        self.empty_filter_enabled = checked
        self.apply_image_list()

    # -------------------- 导航 / 图片切换 --------------------

    def on_image_current_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        self.goto_image(current.row())

    def goto_index(self, idx: int) -> None:
        if not self.image_paths:
            return
        idx = max(0, min(len(self.image_paths) - 1, idx))
        model_idx = self.image_model.index(idx, 0)
        self.image_list.setCurrentIndex(model_idx)
        self.image_list.scrollTo(model_idx)
        if self.current_index != idx:
            self.goto_image(idx)

    def goto_image(self, row: int) -> None:
        if row < 0 or row >= len(self.image_paths):
            return
        if self.current_index != row:
            self.save_current(silent=True)
        self.current_index = row
        path = self.image_paths[row]
        try:
            frame = load_image(path)
        except Exception as exc:
            self.append_log(f"图片读取失败：{path}：{exc}")
            QMessageBox.warning(self, "图片读取失败", f"{path}\n{exc}")
            self.canvas.set_image(None)
            self.canvas.set_annotations([])
            self.current_frame = None
            self.refresh_box_table()
            return
        self.current_frame = frame
        h, w = frame.shape[:2]
        anns = read_labels_file(self.label_path_for_image(path), w, h)
        defects = read_defects_file(self.defect_path_for_image(path), w, h)
        self.canvas.set_image(frame)
        self.canvas.set_labels(self.labels())
        self.canvas.set_annotations(anns)
        self.canvas.set_defects(defects)
        self.info_label.setText(
            f"{row + 1}/{len(self.image_paths)}  {path.name}  {w}×{h}  目标:{len(anns)}  缺陷:{len(self.canvas.defects)}"
        )
        self.image_model.update_box_count(row, len(anns))
        self.sync_full_count(path, len(anns))
        self.refresh_box_table()
        self.canvas.setFocus()

    def sync_full_count(self, path: Path, count: int) -> None:
        try:
            full_idx = self.full_paths.index(path)
            self.full_box_counts[full_idx] = count
        except ValueError:
            pass

    def step_image(self, step: int) -> None:
        if not self.image_paths:
            return
        target = max(0, min(len(self.image_paths) - 1, self.current_index + step))
        if target != self.current_index:
            self.goto_index(target)

    def do_jump(self) -> None:
        text = self.jump_edit.text().strip()
        if not text:
            return
        try:
            n = int(text)
            self.goto_index(n - 1)
            self.jump_edit.clear()
            self.canvas.setFocus()
            return
        except ValueError:
            pass
        for i, path in enumerate(self.image_paths):
            if text.lower() in path.name.lower():
                self.goto_index(i)
                self.jump_edit.clear()
                self.canvas.setFocus()
                return
        QMessageBox.information(self, "未找到", f"没有匹配的图片：{text}")

    # -------------------- 保存 / 表格 --------------------

    def save_current(self, silent: bool = False) -> None:
        if self.current_index < 0 or self.current_frame is None:
            return
        path = self.image_paths[self.current_index]
        dst_img = self.output_image_path(path)
        if path.resolve() != dst_img.resolve():
            try:
                save_image(dst_img, self.current_frame)
            except Exception as exc:
                self.append_log(f"图片保存失败：{exc}")
                return
            # 同步列表与 model 显示
            self.image_paths[self.current_index] = dst_img
            self.image_model.update_path(self.current_index, dst_img)
            try:
                full_idx = self.full_paths.index(path)
                self.full_paths[full_idx] = dst_img
            except ValueError:
                pass
            label_path = self.output_root() / "labels" / "train" / f"{dst_img.stem}.txt"
            defect_path = self.output_root() / "defects" / "train" / f"{dst_img.stem}.json"
        else:
            label_path = self.label_path_for_image(path)
            defect_path = self.defect_path_for_image(path)
        h, w = self.current_frame.shape[:2]
        try:
            write_labels_file(label_path, self.canvas.annotations, w, h)
            write_defects_file(
                defect_path,
                self.canvas.defects,
                w,
                h,
                self.image_paths[self.current_index],
                self.labels(),
            )
        except Exception as exc:
            self.append_log(f"标注写入失败：{exc}")
            return
        self.image_model.update_box_count(self.current_index, len(self.canvas.annotations))
        self.sync_full_count(self.image_paths[self.current_index], len(self.canvas.annotations))
        if not silent:
            self.append_log(f"已保存：{label_path}")

    def refresh_box_table(self) -> None:
        anns = self.canvas.annotations
        self.box_table.setRowCount(len(anns))
        labels = self.labels()
        for row, ann in enumerate(anns):
            name = labels[ann.cls] if 0 <= ann.cls < len(labels) else str(ann.cls)
            if ann.is_box:
                x1, y1, x2, y2 = ann.box_corners()
                values = ["box", name, f"{x1:.0f}", f"{y1:.0f}", f"{x2:.0f}", f"{y2:.0f}"]
            else:
                r = ann.rect()
                values = ["polygon", name, f"{len(ann.points)}点",
                          f"{r.left():.0f},{r.top():.0f}",
                          f"{r.width():.0f}", f"{r.height():.0f}"]
            for col, value in enumerate(values):
                self.box_table.setItem(row, col, QTableWidgetItem(str(value)))
        if self.current_index >= 0:
            self.image_model.update_box_count(self.current_index, len(anns))

        defects = self.canvas.defects
        self.defect_table.setRowCount(len(defects))
        for row, defect in enumerate(defects):
            type_name = DEFECT_TYPE_LABELS.get(defect.defect_type, defect.defect_type)
            severity_name = DEFECT_SEVERITY_LABELS.get(defect.severity, defect.severity)
            values = [
                str(defect.parent_index + 1),
                type_name,
                severity_name,
                str(len(defect.points)),
                defect.note,
                defect.defect_id,
            ]
            for col, value in enumerate(values):
                self.defect_table.setItem(row, col, QTableWidgetItem(str(value)))

    def on_annotations_changed(self) -> None:
        self.refresh_box_table()

    def on_defects_changed(self) -> None:
        self.refresh_box_table()

    def on_selection_changed(self, idx: int) -> None:
        if 0 <= idx < self.box_table.rowCount():
            self.box_table.selectRow(idx)
        else:
            self.box_table.clearSelection()

    def select_box_from_table(self, row: int, col: int) -> None:
        self.canvas.select(row)

    def on_defect_selection_changed(self, idx: int) -> None:
        if 0 <= idx < self.defect_table.rowCount():
            self.defect_table.selectRow(idx)
            defect = self.canvas.defects[idx]
            type_index = self.defect_type_combo.findData(defect.defect_type)
            if type_index >= 0:
                self.defect_type_combo.setCurrentIndex(type_index)
            severity_index = self.defect_severity_combo.findData(defect.severity)
            if severity_index >= 0:
                self.defect_severity_combo.setCurrentIndex(severity_index)
            self.defect_note_edit.setText(defect.note)
        else:
            self.defect_table.clearSelection()

    def select_defect_from_table(self, row: int, col: int) -> None:
        self.canvas.select_defect(row)

    # -------------------- 操作 --------------------

    def delete_selected_box(self) -> None:
        self.canvas.delete_selected()

    def save_and_next(self) -> None:
        if self.current_index < 0:
            return
        self.save_current()
        self.step_image(1)

    def clear_current_boxes(self) -> None:
        if self.current_index < 0:
            return
        self.canvas.clear_annotations()
        self.save_current(silent=True)
        self.append_log("已清空当前图片标注")

    def copy_previous_boxes(self) -> None:
        if self.current_index <= 0 or self.current_frame is None:
            QMessageBox.information(self, "没有上一张", "前面没有可复制的图片")
            return
        prev_path = self.image_paths[self.current_index - 1]
        try:
            prev_frame = load_image(prev_path)
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
            return
        prev_h, prev_w = prev_frame.shape[:2]
        cur_h, cur_w = self.current_frame.shape[:2]
        prev_anns = read_labels_file(self.label_path_for_image(prev_path), prev_w, prev_h)
        prev_defects = read_defects_file(self.defect_path_for_image(prev_path), prev_w, prev_h)
        if not prev_anns:
            QMessageBox.information(self, "没有标注", "上一张图片没有可复制的标注")
            return
        sx = cur_w / prev_w
        sy = cur_h / prev_h
        copied: list[Annotation] = []
        for ann in prev_anns:
            if ann.is_box:
                x1, y1, x2, y2 = ann.box_corners()
                copied.append(Annotation.from_box(ann.cls, x1 * sx, y1 * sy, x2 * sx, y2 * sy))
            else:
                copied.append(Annotation.from_polygon(ann.cls, [(x * sx, y * sy) for x, y in ann.points]))
        self.canvas.set_annotations(copied)
        copied_defects: list[DefectAnnotation] = []
        for defect in prev_defects:
            if not (0 <= defect.parent_index < len(copied)):
                continue
            copied_defect = defect.copy()
            copied_defect.defect_id = uuid.uuid4().hex[:12]
            copied_defect.points = [(x * sx, y * sy) for x, y in defect.points]
            copied_defect.parent_cls = copied[copied_defect.parent_index].cls
            copied_defect.created_at = datetime.now().isoformat(timespec="seconds")
            copied_defects.append(copied_defect)
        self.canvas.set_defects(copied_defects)
        self.canvas.annotations_changed.emit()
        self.canvas.defects_changed.emit()
        self.append_log(f"已复制上一张标注：目标 {len(copied)} 个，缺陷 {len(copied_defects)} 个")

    def goto_next_empty_label(self) -> None:
        if not self.image_paths:
            return
        self.save_current(silent=True)
        start = max(0, self.current_index + 1)
        order = list(range(start, len(self.image_paths))) + list(range(0, start))
        for row in order:
            if self.image_model.box_count(row) == 0:
                self.goto_index(row)
                return
        QMessageBox.information(self, "没有空标注", "当前列表里没有空标注图片")

    def delete_current_frame(self) -> None:
        if self.current_index < 0 or self.current_index >= len(self.image_paths):
            return
        image_path = self.image_paths[self.current_index]
        in_output = self.is_output_image_path(image_path)
        target_label = self.label_path_for_image(image_path)
        target_defect = self.defect_path_for_image(image_path)
        msg = f"确定删除当前图片？\n{image_path.name}"
        if in_output:
            msg += "\n\n图片和标签文件将一并从磁盘删除。"
        else:
            msg += "\n\n注意：图片不在输出目录，仅从列表移除，磁盘原文件保留。"
        reply = QMessageBox.question(
            self, "确认删除", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        row = self.current_index
        if in_output:
            try:
                image_path.unlink(missing_ok=True)
            except OSError as exc:
                self.append_log(f"删除图片失败：{exc}")
            try:
                target_label.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                target_defect.unlink(missing_ok=True)
            except OSError:
                pass
        # 从列表与 full 列表移除
        self.image_paths.pop(row)
        selection_model = self.image_list.selectionModel()
        selection_model.blockSignals(True)
        self.image_model.remove_row(row)
        selection_model.blockSignals(False)
        try:
            full_idx = self.full_paths.index(image_path)
            self.full_paths.pop(full_idx)
            self.full_box_counts.pop(full_idx)
        except ValueError:
            pass
        self.append_log(f"已从列表移除：{image_path.name}")
        # 跳到下一张
        self.current_index = -1
        self.current_frame = None
        self.canvas.set_image(None)
        self.canvas.set_annotations([])
        if self.image_paths:
            target = min(row, len(self.image_paths) - 1)
            self.goto_index(target)
        else:
            self.info_label.setText("未加载")
            self.refresh_box_table()

    def delete_empty_label_frames(self) -> None:
        if not self.image_paths:
            return
        self.save_current(silent=True)
        reply = QMessageBox.question(
            self, "确认批量删除",
            "将后台检查当前列表，删除输出目录中所有空标签帧和对应标签文件。\n请确认这些图片中确实没有目标。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.start_worker(
            DeleteEmptyLabelsWorker(list(self.image_paths), self.output_root()),
            self.scan_output_images,
        )

    # -------------------- AI 任务 --------------------

    def ai_params(self) -> AiParams:
        labels = self.labels()
        selected = max(0, min(self.class_combo.currentIndex(), len(labels) - 1))
        return AiParams(
            weights=self.weights_edit.text(),
            labels=labels,
            selected_cls=selected,
            conf=float(self.conf_spin.value()),
            imgsz=self.imgsz_spin.value(),
            device=self.device_combo.currentText(),
            output_root=self.output_root(),
            task=self.current_task(),
        )

    def ai_label_images(self) -> None:
        image_paths = list(self.image_paths)
        if not image_paths:
            QMessageBox.warning(self, "没有图片", "请先点击\"加载图片\"，再批量标注")
            return
        if not Path(self.weights_edit.text()).exists():
            QMessageBox.warning(self, "权重不存在", f"找不到模型权重：{self.weights_edit.text()}")
            return
        self.start_worker(ImageAutoLabelWorker(image_paths, self.ai_params()), self.scan_output_images)

    def extract_videos(self, do_ai: bool) -> None:
        folder = Path(self.video_folder_edit.text())
        if not folder.exists():
            QMessageBox.warning(self, "目录不存在", f"视频文件夹不存在：{folder}")
            return
        videos = sorted([p for p in folder.rglob("*") if p.suffix.lower() in VIDEO_SUFFIXES])
        if not videos:
            QMessageBox.warning(self, "没有视频", "视频文件夹内没有可抽帧视频")
            return
        if do_ai and not Path(self.weights_edit.text()).exists():
            QMessageBox.warning(self, "权重不存在", f"找不到模型权重：{self.weights_edit.text()}")
            return
        params = self.ai_params() if do_ai else None
        worker = VideoExtractWorker(
            videos,
            self.frame_step_spin.value(),
            self.max_frames_spin.value(),
            self.output_root(),
            self.labels(),
            params,
            self.current_task(),
        )
        self.start_worker(worker, self.scan_output_images)

    # -------------------- 任务通用 --------------------

    def start_worker(self, worker: QObject, on_done_callback) -> None:
        if self.worker_thread is not None:
            QMessageBox.information(self, "任务运行中", "请等待当前任务完成")
            return
        self.set_controls_enabled(False)
        self.progress.show()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.worker_thread = QThread()
        self.worker = worker
        worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(worker.run)
        worker.progress.connect(self.worker_progress)
        worker.done.connect(lambda result: self.worker_done(result, on_done_callback))
        worker.failed.connect(self.worker_failed)
        worker.done.connect(self.worker_thread.quit)
        worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.cleanup_worker)
        self.worker_thread.start()

    def worker_progress(self, current: int, total: int, text: str) -> None:
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(current / total * 100))
        else:
            self.progress.setRange(0, 0)
        self.append_log(f"{current}/{total or '?'} {text}")

    def worker_done(self, result: dict, callback) -> None:
        self.append_log("完成：" + json.dumps(result, ensure_ascii=False))
        self.after_worker_callback = callback

    def worker_failed(self, error: str) -> None:
        self.append_log(error)
        QMessageBox.critical(self, "任务失败", error[:2000])

    def cleanup_worker(self) -> None:
        self.progress.hide()
        self.set_controls_enabled(True)
        self.worker_thread = None
        self.worker = None
        cb = self.after_worker_callback
        self.after_worker_callback = None
        if cb is not None:
            cb()

    def set_controls_enabled(self, enabled: bool) -> None:
        for widget in [
            self.scan_btn, self.ai_btn, self.extract_btn, self.extract_ai_btn,
            self.save_btn, self.delete_btn, self.save_next_btn, self.clear_boxes_btn,
            self.copy_prev_btn, self.next_empty_btn, self.delete_frame_btn,
            self.delete_empty_btn, self.load_yolo_btn,
        ]:
            widget.setEnabled(enabled)

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    # -------------------- 设置持久化 --------------------

    def restore_settings(self) -> None:
        s = self.settings
        for key, edit in [
            ("paths/weights", self.weights_edit),
            ("paths/image_folder", self.image_folder_edit),
            ("paths/video_folder", self.video_folder_edit),
            ("paths/output", self.output_edit),
        ]:
            v = s.value(key, "")
            if v:
                edit.setText(str(v))
        for key, spin, caster in [
            ("ai/conf", self.conf_spin, float),
            ("ai/imgsz", self.imgsz_spin, int),
            ("video/step", self.frame_step_spin, int),
            ("video/max_frames", self.max_frames_spin, int),
        ]:
            v = s.value(key, None)
            if v is not None:
                try:
                    spin.setValue(caster(v))
                except (TypeError, ValueError):
                    pass
        device = s.value("ai/device", "")
        if device and self.device_combo.findText(str(device)) >= 0:
            self.device_combo.setCurrentText(str(device))
        try:
            restored_mode = int(s.value("ui/mode", 0))
            self.mode_combo.setCurrentIndex(restored_mode)
        except (TypeError, ValueError):
            restored_mode = self.mode_combo.currentIndex()
        geom = s.value("ui/geometry")
        if geom is not None:
            try:
                self.restoreGeometry(geom)
            except Exception:
                self.resize(1500, 900)
        else:
            self.resize(1500, 900)
        sizes = s.value("ui/splitter")
        if sizes:
            try:
                self.splitter.setSizes([int(x) for x in sizes])
            except (TypeError, ValueError):
                self.splitter.setSizes([590, 1010])
        else:
            self.splitter.setSizes([590, 1010])
        # 从输出目录恢复标签
        out = self.output_root()
        if (out / "data.yaml").exists():
            self.set_labels_from_yolo_folder(out)
            if 0 <= restored_mode < self.mode_combo.count():
                self.mode_combo.setCurrentIndex(restored_mode)

    def save_settings(self) -> None:
        s = self.settings
        s.setValue("paths/weights", self.weights_edit.text())
        s.setValue("paths/image_folder", self.image_folder_edit.text())
        s.setValue("paths/video_folder", self.video_folder_edit.text())
        s.setValue("paths/output", self.output_edit.text())
        s.setValue("ai/conf", float(self.conf_spin.value()))
        s.setValue("ai/imgsz", int(self.imgsz_spin.value()))
        s.setValue("ai/device", self.device_combo.currentText())
        s.setValue("video/step", int(self.frame_step_spin.value()))
        s.setValue("video/max_frames", int(self.max_frames_spin.value()))
        s.setValue("ui/mode", int(self.mode_combo.currentIndex()))
        s.setValue("ui/geometry", self.saveGeometry())
        s.setValue("ui/splitter", self.splitter.sizes())
        s.setValue("ui/last_image_index", self.current_index if self.current_index >= 0 else 0)

    def closeEvent(self, event) -> None:
        try:
            self.save_current(silent=True)
        except Exception:
            pass
        self.save_settings()
        super().closeEvent(event)


# ====================================================================
# 入口
# ====================================================================


def main() -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    if "--qt-import-test" in sys.argv:
        print(f"QtCore import ok: {qVersion()}")
        return 0
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(VSCODE_DARK_QSS)
    app.setApplicationName(SETTINGS_APP)
    app.setOrganizationName(SETTINGS_ORG)
    if "--qapplication-test" in sys.argv:
        print("QApplication ok")
        return 0
    window = MainWindow()
    if "--window-smoke-test" in sys.argv:
        window.show()
        app.processEvents()
        window.close()
        print("v2 window ok")
        return 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
