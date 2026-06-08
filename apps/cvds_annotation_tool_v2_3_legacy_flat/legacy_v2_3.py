"""
CVDS AI 辅助 YOLO 标注工具 v2.3

v2.2 新增：
- 全局 Undo/Redo 栈（Ctrl+Z / Ctrl+Y 或 Ctrl+Shift+Z），覆盖添加/删除/拖拽/
  类别修改/缺陷增删改/SAM 接受 等全部编辑动作，按图片独立维护历史
- 缺陷层支持三种形状：多边形 / 矩形框 / 单点（point 适合小缺陷快速打点）
- SAM 半自动分割：Alt+S 进入，左键拉框出预览 mask，Shift+左键 加正点，
  右键 加负点修正，回车 接受为正式标注；后台线程推理，节流，自动复用
  image embedding；输出经 Douglas-Peucker 简化的 polygon

继承自 v2 的特性：
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

from cvds_annotation_tool import APP_VERSION
from cvds_annotation_tool.constants import SETTINGS_APP as V23_SETTINGS_APP
from cvds_annotation_tool.runtime_paths import RuntimePaths
from cvds_annotation_tool.services.backup_service import atomic_write_text, backup_existing_file, move_dataset_item_to_trash
from cvds_annotation_tool.services.dataset_export import export_dataset
from cvds_annotation_tool.services.dataset_quality import audit_dataset
from cvds_annotation_tool.services.diagnostics import diagnose_environment


DLL_DIRECTORY_HANDLES: list[object] = []
RUNTIME_PATHS = RuntimePaths()


def relaunch_source_with_ai_python() -> None:
    """v2.3 不再自动跳转到开发机 Anaconda 环境。"""
    return


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


configure_qt_runtime_paths()

import yaml  # noqa: E402
from PySide6.QtCore import (  # noqa: E402
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
from PySide6.QtGui import (  # noqa: E402
    QBrush,
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QShortcut,
)
from PySide6.QtWidgets import (  # noqa: E402
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
DEFECT_META_VERSION = 3  # v2.3: 安全保存、质检、导出 schema
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

# v2.2 新增：缺陷形状
DEFECT_KINDS = ("polygon", "box", "point")
DEFECT_KIND_LABELS = {
    "polygon": "多边形",
    "box": "矩形框",
    "point": "单点",
}
DEFECT_POINT_RADIUS_PX = 8.0  # 点形缺陷的命中半径(图像像素)

# v2.2 新增：SAM 相关常量
SAM_MODE_NAME = "SAM 半自动 (segment)"
SAM_PREVIEW_COLOR = QColor("#22c55e")
SAM_POS_POINT_COLOR = QColor("#22c55e")
SAM_NEG_POINT_COLOR = QColor("#ef4444")
SAM_BOX_COLOR = QColor("#22c55e")
DEFAULT_SAM_WEIGHTS = "mobile_sam.pt"  # ultralytics 会自动下载
SAM_PRESETS = [
    ("MobileSAM (40MB, ~80ms)", "mobile_sam.pt"),
    ("SAM2.1 Tiny (78MB)", "sam2.1_t.pt"),
    ("SAM2.1 Small (185MB)", "sam2.1_s.pt"),
    ("SAM ViT-B (375MB)", "sam_b.pt"),
]

# v2.2 新增：history
HISTORY_MAX_SIZE = 100

SETTINGS_ORG = "CVDS"
SETTINGS_APP = V23_SETTINGS_APP
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


ROOT = RUNTIME_PATHS.install_dir
DEFAULT_WEIGHTS = RUNTIME_PATHS.default_weights_path
DEFAULT_OUTPUT = RUNTIME_PATHS.default_output_dir
DEFAULT_IMAGE_FOLDER = RUNTIME_PATHS.default_image_dir
DEFAULT_VIDEO_FOLDER = RUNTIME_PATHS.default_video_dir


# ====================================================================
# 延迟导入 ultralytics（启动加速关键点）
# ====================================================================

_YOLO_CLS = None
_SAM_CLS = None
_CV2_MODULE = None
_NP_MODULE = None


def get_yolo_cls():
    global _YOLO_CLS
    if _YOLO_CLS is None:
        from ultralytics import YOLO  # 延迟到真正用时再加载
        _YOLO_CLS = YOLO
    return _YOLO_CLS


def get_sam_cls():
    """延迟导入 ultralytics.SAM。"""
    global _SAM_CLS
    if _SAM_CLS is None:
        try:
            from ultralytics import SAM
        except Exception:  # noqa: BLE001
            from ultralytics.models.sam import SAM
        _SAM_CLS = SAM
    return _SAM_CLS


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
    """目标内部缺陷层：独立保存，并通过 parent_index 绑定到一个包裹/目标实例。

    v2.2 起支持三种形状：
    - kind='polygon': 任意多边形，points 是顶点列表（至少 3 个点）
    - kind='box':     矩形框，points 含两个点 [(x1,y1),(x2,y2)]
    - kind='point':   单点缺陷，points 含一个点 [(x,y)]
    """

    defect_id: str
    parent_index: int
    parent_cls: int
    defect_type: str = "hole"
    severity: str = "medium"
    kind: str = "polygon"  # v2.2: polygon/box/point
    points: list[tuple[float, float]] = field(default_factory=list)
    note: str = ""
    created_at: str = ""

    @property
    def is_polygon(self) -> bool:
        return self.kind == "polygon"

    @property
    def is_box(self) -> bool:
        return self.kind == "box"

    @property
    def is_point(self) -> bool:
        return self.kind == "point"

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
            kind="polygon",
            points=[(float(x), float(y)) for x, y in points],
            note=note,
            created_at=created_at or datetime.now().isoformat(timespec="seconds"),
        )

    @classmethod
    def from_box(
        cls_,
        parent_index: int,
        parent: Annotation,
        defect_type: str,
        severity: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
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
            kind="box",
            points=[(float(x1), float(y1)), (float(x2), float(y2))],
            note=note,
            created_at=created_at or datetime.now().isoformat(timespec="seconds"),
        )

    @classmethod
    def from_point(
        cls_,
        parent_index: int,
        parent: Annotation,
        defect_type: str,
        severity: str,
        x: float,
        y: float,
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
            kind="point",
            points=[(float(x), float(y))],
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
            self.kind,
            list(self.points),
            self.note,
            self.created_at,
        )

    def rect(self) -> QRectF:
        if not self.points:
            return QRectF()
        if self.is_point:
            x, y = self.points[0]
            r = DEFECT_POINT_RADIUS_PX
            return QRectF(x - r, y - r, 2 * r, 2 * r)
        if self.is_box and len(self.points) >= 2:
            x1, y1 = self.points[0]
            x2, y2 = self.points[1]
            left, right = sorted([x1, x2])
            top, bottom = sorted([y1, y2])
            return QRectF(left, top, right - left, bottom - top)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def contains(self, x: float, y: float) -> bool:
        if not self.points:
            return False
        if self.is_point:
            px, py = self.points[0]
            r = DEFECT_POINT_RADIUS_PX
            return (x - px) ** 2 + (y - py) ** 2 <= r * r
        if self.is_box and len(self.points) >= 2:
            return self.rect().contains(QPointF(x, y))
        if len(self.points) < 3:
            return False
        poly = QPolygonF([QPointF(px, py) for px, py in self.points])
        return poly.containsPoint(QPointF(x, y), Qt.OddEvenFill)

    def is_valid(self) -> bool:
        """形状是否完整可保存。"""
        if self.is_point:
            return len(self.points) == 1
        if self.is_box:
            if len(self.points) < 2:
                return False
            r = self.rect()
            return r.width() >= 1 and r.height() >= 1
        return len(self.points) >= 3

    def to_json(self, width: int, height: int, labels: list[str]) -> dict:
        parent_name = labels[self.parent_cls] if 0 <= self.parent_cls < len(labels) else str(self.parent_cls)
        return {
            "id": self.defect_id,
            "parent_index": self.parent_index,
            "parent_cls": self.parent_cls,
            "parent_label": parent_name,
            "type": self.defect_type,
            "severity": self.severity,
            "kind": self.kind,
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
        # v2.2: 读 kind，向后兼容 v1 数据（无 kind 字段时按 polygon 处理）
        kind = str(item.get("kind") or "polygon")
        if kind not in DEFECT_KINDS:
            kind = "polygon"
        # 形状对应的最少点数校验
        min_points = {"polygon": 3, "box": 2, "point": 1}.get(kind, 3)
        if len(points) < min_points:
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
            kind=kind,
            points=points,
            note=str(item.get("note") or ""),
            created_at=str(item.get("created_at") or ""),
        )


# ====================================================================
# v2.2 历史栈 (Undo/Redo)
# ====================================================================


@dataclass
class CanvasSnapshot:
    """画布编辑状态的不可变快照。

    用 deep copy 而非引用，保证 push 之后再修改 canvas.annotations
    不会污染历史栈中的快照。
    """

    annotations: list["Annotation"]
    defects: list["DefectAnnotation"]
    selected: int = -1
    selected_defect: int = -1

    @classmethod
    def capture(cls, canvas) -> "CanvasSnapshot":
        return cls(
            annotations=[a.copy() for a in canvas.annotations],
            defects=[d.copy() for d in canvas.defects],
            selected=canvas.selected,
            selected_defect=canvas.selected_defect,
        )

    def apply_to(self, canvas) -> None:
        canvas.annotations = [a.copy() for a in self.annotations]
        canvas.defects = [d.copy() for d in self.defects]
        canvas.selected = self.selected if 0 <= self.selected < len(canvas.annotations) else -1
        canvas.selected_defect = (
            self.selected_defect if 0 <= self.selected_defect < len(canvas.defects) else -1
        )


class HistoryManager:
    """每张图片独立维护的 undo/redo 栈。

    用法：
        - 在执行任何修改前调用 push(snapshot) 保存当前状态
        - undo() 返回应该恢复的快照，并把当前状态推到 redo 栈
        - redo() 反之
        - 切图、清空 等场景调用 clear()
    """

    def __init__(self, max_size: int = HISTORY_MAX_SIZE) -> None:
        self.undo_stack: list[CanvasSnapshot] = []
        self.redo_stack: list[CanvasSnapshot] = []
        self.max_size = max_size

    def push(self, snapshot: CanvasSnapshot) -> None:
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.max_size:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def undo(self, current: CanvasSnapshot) -> CanvasSnapshot | None:
        if not self.undo_stack:
            return None
        self.redo_stack.append(current)
        return self.undo_stack.pop()

    def redo(self, current: CanvasSnapshot) -> CanvasSnapshot | None:
        if not self.redo_stack:
            return None
        self.undo_stack.append(current)
        return self.redo_stack.pop()

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()


# ====================================================================
# v2.2 SAM 半自动分割
# ====================================================================


def simplify_polygon(
    points: list[tuple[float, float]],
    min_vertices: int = 4,
    relative_epsilon: float = 0.003,
) -> list[tuple[float, float]]:
    """用 Douglas-Peucker 把 SAM 输出的稠密轮廓简化。

    SAM 原始输出常有几百个顶点，直接落到 YOLO seg 标签会让文件巨大、
    画布拖动卡顿。按周长比例自适应 epsilon，典型结果在 20-80 顶点。
    """
    if len(points) < min_vertices:
        return points
    cv2 = get_cv2()
    np = get_np()
    contour = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
    perimeter = cv2.arcLength(contour, True)
    if perimeter <= 0:
        return points
    eps = max(1.0, perimeter * relative_epsilon)
    approx = cv2.approxPolyDP(contour, eps, True)
    simplified = [(float(p[0][0]), float(p[0][1])) for p in approx]
    return simplified if len(simplified) >= 3 else points


@dataclass
class SamRequest:
    kind: str  # 'box' or 'points'
    bbox: tuple[float, float, float, float] | None = None
    points: list[tuple[float, float]] | None = None
    labels: list[int] | None = None
    image_id: str = ""


class SamService(QObject):
    """运行在工作线程，封装 SAM 模型加载和单次 prompt 推理。"""

    mask_ready = Signal(object, str)  # polygon, image_id
    failed = Signal(str)
    loaded = Signal(str)

    def __init__(self, weights: str, device: str) -> None:
        super().__init__()
        self.weights = weights
        self.device = device
        self.model = None
        self._current_frame = None  # numpy ndarray
        self._current_image_id: str = ""

    def ensure_model(self) -> None:
        if self.model is None:
            SAM = get_sam_cls()
            self.model = SAM(self.weights)
            self.loaded.emit(self.weights)

    def set_image(self, frame, image_id: str) -> None:
        self._current_frame = frame
        self._current_image_id = image_id

    def handle_request(self, request: SamRequest) -> None:
        try:
            self.ensure_model()
            if self._current_frame is None:
                self.failed.emit("当前没有图片可供 SAM 推理")
                return
            if request.image_id and request.image_id != self._current_image_id:
                # 用户已经翻页，丢弃过期请求
                return
            if request.kind == "box" and request.bbox is not None:
                result = self.model.predict(
                    self._current_frame,
                    bboxes=[list(request.bbox)],
                    device=self.device,
                    verbose=False,
                )[0]
            elif request.kind == "points" and request.points:
                result = self.model.predict(
                    self._current_frame,
                    points=[list(request.points)],
                    labels=[list(request.labels or [1] * len(request.points))],
                    device=self.device,
                    verbose=False,
                )[0]
            else:
                self.failed.emit("无效的 SAM 请求")
                return
            polygon = self._extract_polygon(result)
            if polygon is None:
                self.failed.emit("SAM 未返回有效 mask")
                return
            self.mask_ready.emit(polygon, self._current_image_id)
        except Exception:
            self.failed.emit(traceback.format_exc())

    def release(self) -> None:
        self.model = None
        self._current_frame = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    @staticmethod
    def _extract_polygon(result) -> list[tuple[float, float]] | None:
        masks = getattr(result, "masks", None)
        if masks is None:
            return None
        try:
            xy = masks.xy
        except Exception:  # noqa: BLE001
            return None
        if not xy or len(xy[0]) < 3:
            return None
        raw = [(float(x), float(y)) for x, y in xy[0]]
        return simplify_polygon(raw)


class SamController(QObject):
    """主线程调度器，负责把请求发到 SamService、做节流。"""

    request_to_service = Signal(SamRequest)
    mask_ready = Signal(object, str)
    failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, weights: str, device: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.weights = weights
        self.device = device
        self.thread = QThread()
        self.service = SamService(weights, device)
        self.service.moveToThread(self.thread)
        self.request_to_service.connect(self.service.handle_request)
        self.service.mask_ready.connect(self._on_mask)
        self.service.failed.connect(self._on_failed)
        self._busy = False
        self._pending: SamRequest | None = None
        self.thread.start()

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busy_changed.emit(busy)

    def set_image(self, frame, image_id: str) -> None:
        self.service.set_image(frame, image_id)

    def submit(self, request: SamRequest) -> None:
        if self._busy:
            # 推理中：只保留最新请求，避免在快速连点时积压
            self._pending = request
            return
        self._set_busy(True)
        self.request_to_service.emit(request)

    def _on_mask(self, polygon, image_id: str) -> None:
        self._set_busy(False)
        self.mask_ready.emit(polygon, image_id)
        if self._pending is not None:
            pending = self._pending
            self._pending = None
            self.submit(pending)

    def _on_failed(self, msg: str) -> None:
        self._set_busy(False)
        self.failed.emit(msg)
        if self._pending is not None:
            pending = self._pending
            self._pending = None
            self.submit(pending)

    def shutdown(self) -> None:
        try:
            self.service.release()
        except Exception:  # noqa: BLE001
            pass
        self.thread.quit()
        self.thread.wait(3000)


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
    backup_existing_file(path, RUNTIME_PATHS.backups_dir, "label")
    atomic_write_text(path, payload)


def ensure_empty_label(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, "")


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
                "description": "CVDS 目标内部缺陷层，按 parent_index 绑定 YOLO 目标，支持 polygon/box/point。",
                "types": {name: DEFECT_TYPE_LABELS[name] for name in DEFECT_TYPES},
                "severities": list(DEFECT_SEVERITIES),
                "kinds": list(DEFECT_KINDS),
            },
        }
        atomic_write_text(output_root / "data.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
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
        if defect.parent_index >= 0 and defect.is_valid()
    ]
    if not valid_defects:
        if path.exists():
            backup_existing_file(path, RUNTIME_PATHS.backups_dir, "defect")
            path.unlink()
        return
    payload = {
        "version": DEFECT_META_VERSION,
        "image": image_path.name,
        "size": {"width": width, "height": height},
        "defects": [defect.to_json(width, height, labels) for defect in valid_defects],
    }
    backup_existing_file(path, RUNTIME_PATHS.backups_dir, "defect")
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


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
            prefix = "空" if count == 0 else "标"
            return f"{index.row() + 1}.[{prefix}:{count}] {path.name}"
        if role == Qt.ToolTipRole:
            return str(path)
        if role == Qt.UserRole:
            return int(self.box_counts[index.row()])
        if role == Qt.ForegroundRole:
            return QBrush(QColor("#fbbf24") if self.box_counts[index.row()] == 0 else QColor("#93c5fd"))
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
    # v2.2 新增：history 钩子。在执行任何"破坏性"修改前发出，
    # 由 MainWindow 决定是否 push 到 undo 栈。canvas 不直接持有 history，
    # 这样保持类的可测试性。
    pre_edit = Signal()
    # v2.2 新增：SAM 相关信号
    sam_box_committed = Signal(float, float, float, float)
    sam_point_added = Signal(float, float, int)  # x, y, label(1/0)
    sam_accept_requested = Signal()
    sam_accept_defect_requested = Signal()
    sam_cancel_requested = Signal()

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
        self.mode = "box"  # 'box' / 'polygon' / 'defect' / 'sam'
        self.selected = -1
        self.selected_defect = -1
        self.current_defect_type = "hole"
        self.current_defect_severity = "medium"
        self.current_defect_note = ""
        # v2.2: 缺陷形状
        self.current_defect_kind = "polygon"  # 'polygon' / 'box' / 'point'

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

        # 目标内部缺陷绘制(多边形形)
        self.drawing_defect = False
        self.defect_points: list[tuple[float, float]] = []
        self.defect_cursor: QPointF | None = None
        # v2.2: 缺陷形状下的矩形绘制
        self.drawing_defect_box = False
        self.defect_box_start: QPointF | None = None
        self.defect_box_current: QPointF | None = None

        # 拖拽
        self.drag_mode: str | None = None  # 'move' / 'resize' / 'vertex' / 'pan'
        self.drag_start_img: QPointF | None = None
        self.drag_original_ann: Annotation | None = None
        self.drag_original_defects: list[DefectAnnotation] = []
        self.resize_handle: str | None = None
        self.vertex_index = -1
        self.drag_changed = False
        self.pan_last: QPoint | None = None

        # v2.2: SAM 模式状态
        self.sam_active = False
        self.sam_drawing_box = False
        self.sam_box_start: QPointF | None = None
        self.sam_box_current: QPointF | None = None
        self.sam_points: list[tuple[float, float]] = []
        self.sam_labels: list[int] = []
        self.sam_preview_polygon: list[tuple[float, float]] | None = None
        self.sam_busy = False  # 推理进行中的提示

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

    def set_defect_meta(self, defect_type: str, severity: str, note: str = "", kind: str | None = None) -> None:
        self.current_defect_type = defect_type if defect_type in DEFECT_TYPES else "other"
        self.current_defect_severity = severity if severity in DEFECT_SEVERITIES else "medium"
        self.current_defect_note = note.strip()
        if kind is not None and kind in DEFECT_KINDS:
            if kind != self.current_defect_kind:
                self.current_defect_kind = kind
                # 切换形状时，清理进行中的缺陷绘制
                self._reset_defect_drawing()
                self.update()

    def set_selected_class(self, cls: int) -> None:
        if 0 <= self.selected < len(self.annotations):
            self.pre_edit.emit()
            self.annotations[self.selected].cls = int(cls)
            for defect in self.defects:
                if defect.parent_index == self.selected:
                    defect.parent_cls = int(cls)
            self.annotations_changed.emit()
            self.defects_changed.emit()
            self.update()

    def set_mode(self, mode: str) -> None:
        if mode in ("box", "polygon", "defect", "sam") and mode != self.mode:
            self.mode = mode
            self.sam_active = (mode == "sam")
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
            self.pre_edit.emit()
            self.defects.pop(self.selected_defect)
            self.selected_defect = -1
            self.defect_selection_changed.emit(-1)
            self.defects_changed.emit()
            self.update()
            return
        if 0 <= self.selected < len(self.annotations):
            self.pre_edit.emit()
            deleted_index = self.selected
            self.annotations.pop(deleted_index)
            self._remove_or_reindex_defects_for_deleted_parent(deleted_index)
            self.selected = -1
            self.selection_changed.emit(-1)
            self.annotations_changed.emit()
            self.defects_changed.emit()
            self.update()

    def rollback_current_action(self) -> bool:
        # v2.2: SAM 模式优先
        if self.sam_active:
            if self.sam_preview_polygon or self.sam_points:
                self.sam_preview_polygon = None
                self.sam_points = []
                self.sam_labels = []
                self.sam_cancel_requested.emit()
                self.update()
                return True
            if self.sam_drawing_box:
                self.sam_drawing_box = False
                self.sam_box_start = None
                self.sam_box_current = None
                self.update()
                return True
        # v2.2: 缺陷-矩形框绘制中
        if self.drawing_defect_box:
            self.drawing_defect_box = False
            self.defect_box_start = None
            self.defect_box_current = None
            self.update()
            return True
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
            self.pre_edit.emit()
            self.annotations = []
            self.defects = []
            self.selected = -1
            self.selected_defect = -1
            self.selection_changed.emit(-1)
            self.defect_selection_changed.emit(-1)
            self.annotations_changed.emit()
            self.defects_changed.emit()
            self.update()

    def _reset_defect_drawing(self) -> None:
        self.drawing_defect = False
        self.defect_points = []
        self.defect_cursor = None
        self.drawing_defect_box = False
        self.defect_box_start = None
        self.defect_box_current = None

    def _reset_sam_state(self) -> None:
        self.sam_drawing_box = False
        self.sam_box_start = None
        self.sam_box_current = None
        self.sam_points = []
        self.sam_labels = []
        self.sam_preview_polygon = None

    def _reset_interaction(self) -> None:
        self.drawing_box = False
        self.box_start = None
        self.box_current = None
        self.drawing_polygon = False
        self.polygon_points = []
        self.polygon_cursor = None
        self._reset_defect_drawing()
        self._reset_sam_state()
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
        image_point = self.widget_to_image(event.position()) if event.button() != Qt.RightButton else self.widget_to_image(event.position())

        # ===== v2.2 SAM 模式 =====
        if self.sam_active:
            if event.button() == Qt.RightButton:
                if self.sam_preview_polygon and image_point is not None:
                    # 右键 + 已有预览 -> 加负点
                    self.sam_points.append((image_point.x(), image_point.y()))
                    self.sam_labels.append(0)
                    self.sam_point_added.emit(image_point.x(), image_point.y(), 0)
                    self.update()
                    return
                # 右键无预览 -> 取消
                self._reset_sam_state()
                self.sam_cancel_requested.emit()
                self.update()
                return
            if event.button() == Qt.LeftButton and image_point is not None:
                if event.modifiers() & Qt.ShiftModifier:
                    # Shift+左键 -> 加正点
                    self.sam_points.append((image_point.x(), image_point.y()))
                    self.sam_labels.append(1)
                    self.sam_point_added.emit(image_point.x(), image_point.y(), 1)
                    self.update()
                    return
                # 左键 -> 开始拉框
                self.sam_drawing_box = True
                self.sam_box_start = image_point
                self.sam_box_current = image_point
                self.update()
                return
            return

        # ===== 右键完成/取消 =====
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
        if image_point is None:
            return

        # 正在画缺陷多边形
        if self.drawing_defect:
            if self.point_inside_selected_parent(image_point):
                self.defect_points.append((image_point.x(), image_point.y()))
                self.defect_cursor = image_point
                self.update()
            return
        # 正在画目标多边形
        if self.drawing_polygon:
            self.polygon_points.append((image_point.x(), image_point.y()))
            self.polygon_cursor = image_point
            self.update()
            return

        # ===== 缺陷模式 =====
        if self.mode == "defect":
            defect_hit = self.hit_defect(image_point)
            if defect_hit >= 0:
                self.select_defect(defect_hit)
                return
            parent = self.selected_parent_for_defect()
            if parent >= 0 and self.annotations[parent].contains(image_point.x(), image_point.y()):
                # v2.2: 根据当前缺陷形状决定如何开始绘制
                if self.current_defect_kind == "point":
                    # 单点缺陷：左键直接落点完成
                    self._commit_defect_point(image_point.x(), image_point.y())
                    return
                if self.current_defect_kind == "box":
                    self.drawing_defect_box = True
                    self.defect_box_start = image_point
                    self.defect_box_current = image_point
                    self.update()
                    return
                # polygon 默认
                self.drawing_defect = True
                self.defect_points = [(image_point.x(), image_point.y())]
                self.defect_cursor = image_point
                self.update()
                return
            # 没点到任何目标内部，尝试选中标注
            hit = self.hit_test(image_point)
            if hit >= 0:
                self.select(hit)
                return
            return

        # ===== 普通选中/拖拽 =====
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
        # v2.2: SAM 拉框
        if self.sam_drawing_box:
            self.sam_box_current = image_point
            self.update()
            return
        # v2.2: 缺陷-矩形框拉伸
        if self.drawing_defect_box:
            self.defect_box_current = image_point
            self.update()
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
        # v2.2: SAM 拉框释放 -> 提交请求
        if self.sam_drawing_box and event.button() == Qt.LeftButton:
            self.sam_drawing_box = False
            if self.sam_box_start is not None and self.sam_box_current is not None:
                x1, y1 = self.sam_box_start.x(), self.sam_box_start.y()
                x2, y2 = self.sam_box_current.x(), self.sam_box_current.y()
                if abs(x2 - x1) >= 5 and abs(y2 - y1) >= 5:
                    left, right = sorted([x1, x2])
                    top, bottom = sorted([y1, y2])
                    self.sam_box_committed.emit(left, top, right, bottom)
                else:
                    # 过小当作单点正点
                    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                    self.sam_points.append((cx, cy))
                    self.sam_labels.append(1)
                    self.sam_point_added.emit(cx, cy, 1)
            self.sam_box_start = None
            self.sam_box_current = None
            self.update()
            return
        # v2.2: 缺陷-矩形框释放 -> 提交缺陷
        if self.drawing_defect_box and event.button() == Qt.LeftButton:
            self.drawing_defect_box = False
            if self.defect_box_start is not None and self.defect_box_current is not None:
                x1, y1 = self.defect_box_start.x(), self.defect_box_start.y()
                x2, y2 = self.defect_box_current.x(), self.defect_box_current.y()
                if abs(x2 - x1) >= 3 and abs(y2 - y1) >= 3:
                    self._commit_defect_box(x1, y1, x2, y2)
            self.defect_box_start = None
            self.defect_box_current = None
            self.update()
            return
        if self.drag_mode in ("move", "resize", "vertex"):
            if self.drag_changed and 0 <= self.selected < len(self.annotations):
                ann = self.annotations[self.selected]
                if ann.is_box and (ann.rect().width() < 2 or ann.rect().height() < 2):
                    # 拖拽结果无效，静默回滚不入 history
                    if self.drag_original_ann is not None:
                        self.annotations[self.selected] = self.drag_original_ann
                        self.defects = [defect.copy() for defect in self.drag_original_defects]
                else:
                    # 把拖拽后的状态先存起来
                    final_ann = self.annotations[self.selected].copy()
                    final_defects = [d.copy() for d in self.defects]
                    # 临时回到拖拽前状态，让 pre_edit 抓到正确的 "拖拽前" 快照
                    if self.drag_original_ann is not None:
                        self.annotations[self.selected] = self.drag_original_ann.copy()
                        self.defects = [d.copy() for d in self.drag_original_defects]
                    self.pre_edit.emit()
                    # 应用拖拽结果
                    self.annotations[self.selected] = final_ann
                    self.defects = final_defects
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
                self.pre_edit.emit()
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
        self.pre_edit.emit()
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
        self.pre_edit.emit()
        self.defects.append(defect)
        self.drawing_defect = False
        self.defect_points = []
        self.defect_cursor = None
        self.select_defect(len(self.defects) - 1)
        self.defects_changed.emit()
        self.update()

    def _commit_defect_box(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """v2.2: 用矩形框创建缺陷标注。要求父框已选中且两个端点都在父框内。"""
        parent_index = self.selected_parent_for_defect()
        if parent_index < 0 or parent_index >= len(self.annotations):
            return
        parent = self.annotations[parent_index]
        # 把两端点都裁剪到父框内
        prect = parent.rect()
        x1c = max(prect.left(), min(prect.right(), x1))
        y1c = max(prect.top(), min(prect.bottom(), y1))
        x2c = max(prect.left(), min(prect.right(), x2))
        y2c = max(prect.top(), min(prect.bottom(), y2))
        left, right = sorted([x1c, x2c])
        top, bottom = sorted([y1c, y2c])
        if right - left < 2 or bottom - top < 2:
            return
        defect = DefectAnnotation.from_box(
            parent_index,
            parent,
            self.current_defect_type,
            self.current_defect_severity,
            left,
            top,
            right,
            bottom,
            self.current_defect_note,
        )
        self.pre_edit.emit()
        self.defects.append(defect)
        self.select_defect(len(self.defects) - 1)
        self.defects_changed.emit()
        self.update()

    def _commit_defect_point(self, x: float, y: float) -> None:
        """v2.2: 单点缺陷。"""
        parent_index = self.selected_parent_for_defect()
        if parent_index < 0 or parent_index >= len(self.annotations):
            return
        parent = self.annotations[parent_index]
        if not parent.contains(x, y):
            return
        defect = DefectAnnotation.from_point(
            parent_index,
            parent,
            self.current_defect_type,
            self.current_defect_severity,
            x,
            y,
            self.current_defect_note,
        )
        self.pre_edit.emit()
        self.defects.append(defect)
        self.select_defect(len(self.defects) - 1)
        self.defects_changed.emit()
        self.update()

    # ---------- v2.2 SAM 接受/取消接口 ----------

    def sam_set_preview(self, polygon: list[tuple[float, float]] | None) -> None:
        self.sam_preview_polygon = polygon
        self.update()

    def sam_set_busy(self, busy: bool) -> None:
        self.sam_busy = busy
        self.update()

    def sam_accept(self, parent_index: int = -1, as_defect: bool = False) -> bool:
        """把当前 SAM 预览 polygon 提交为正式标注。

        Args:
            parent_index: 当 as_defect=True 时指定父框，否则忽略
            as_defect: 是否提交为缺陷（默认作为目标标注）
        Returns:
            是否成功提交
        """
        polygon = self.sam_preview_polygon
        if not polygon or len(polygon) < 3:
            return False
        if as_defect:
            if not (0 <= parent_index < len(self.annotations)):
                return False
            parent = self.annotations[parent_index]
            clipped = [(x, y) for x, y in polygon if parent.contains(x, y)]
            if len(clipped) < 3:
                return False
            defect = DefectAnnotation.from_polygon(
                parent_index,
                parent,
                self.current_defect_type,
                self.current_defect_severity,
                clipped,
                self.current_defect_note,
            )
            self.pre_edit.emit()
            self.defects.append(defect)
            self.select_defect(len(self.defects) - 1)
            self.defects_changed.emit()
        else:
            ann = Annotation.from_polygon(self.current_cls, polygon)
            self.pre_edit.emit()
            self.annotations.append(ann)
            self.select(len(self.annotations) - 1)
            self.annotations_changed.emit()
        # 重置 SAM 状态，准备下一次
        self.sam_preview_polygon = None
        self.sam_points = []
        self.sam_labels = []
        self.update()
        return True

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
            # v2.2: SAM 模式下回车 = 请求接受预览
            if self.sam_active and self.sam_preview_polygon:
                if event.modifiers() & Qt.ControlModifier:
                    self.sam_accept_defect_requested.emit()
                else:
                    self.sam_accept_requested.emit()
                return
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
            if not (0 <= defect.parent_index < len(self.annotations)):
                continue
            if not defect.is_valid():
                continue
            base_color = DEFECT_COLORS.get(defect.defect_type, DEFECT_COLORS["other"])
            color = SELECTED_COLOR if idx == self.selected_defect else base_color
            pen_width = 3 if idx == self.selected_defect else 2
            if defect.is_polygon:
                pts = [self.image_to_widget(x, y) for x, y in defect.points]
                poly = QPolygonF(pts)
                fill = QColor(color)
                fill.setAlpha(105 if idx == self.selected_defect else 78)
                painter.setPen(QPen(color, pen_width, Qt.DashLine))
                painter.setBrush(fill)
                painter.drawPolygon(poly)
                if idx == self.selected_defect:
                    self._draw_handles(painter, pts)
            elif defect.is_box:
                d_rect = defect.rect()
                tl = self.image_to_widget(d_rect.left(), d_rect.top())
                br = self.image_to_widget(d_rect.right(), d_rect.bottom())
                wr = QRectF(tl, br).normalized()
                fill = QColor(color)
                fill.setAlpha(95 if idx == self.selected_defect else 60)
                painter.setPen(QPen(color, pen_width, Qt.DashLine))
                painter.setBrush(fill)
                painter.drawRect(wr)
                if idx == self.selected_defect:
                    self._draw_handles(painter, [wr.topLeft(), wr.topRight(), wr.bottomLeft(), wr.bottomRight()])
            elif defect.is_point:
                x, y = defect.points[0]
                center = self.image_to_widget(x, y)
                r_screen = max(8, int(DEFECT_POINT_RADIUS_PX * self.effective_scale()))
                # 实心圆 + 十字
                fill = QColor(color)
                fill.setAlpha(160 if idx == self.selected_defect else 120)
                painter.setPen(QPen(color, pen_width))
                painter.setBrush(fill)
                painter.drawEllipse(center, r_screen, r_screen)
                painter.setPen(QPen(QColor("#0b0f16"), 2))
                painter.drawLine(QPointF(center.x() - r_screen + 2, center.y()),
                                 QPointF(center.x() + r_screen - 2, center.y()))
                painter.drawLine(QPointF(center.x(), center.y() - r_screen + 2),
                                 QPointF(center.x(), center.y() + r_screen - 2))
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

        # v2.2: 缺陷矩形拉伸预览
        if self.drawing_defect_box and self.defect_box_start and self.defect_box_current:
            color = DEFECT_COLORS.get(self.current_defect_type, DEFECT_COLORS["other"])
            x1, y1 = self.defect_box_start.x(), self.defect_box_start.y()
            x2, y2 = self.defect_box_current.x(), self.defect_box_current.y()
            left, right = sorted([x1, x2])
            top, bottom = sorted([y1, y2])
            tl = self.image_to_widget(left, top)
            br = self.image_to_widget(right, bottom)
            painter.setPen(QPen(color, 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(tl, br))

        # v2.2: SAM 预览/拉框/点
        if self.sam_active:
            if self.sam_drawing_box and self.sam_box_start and self.sam_box_current:
                tl = self.image_to_widget(min(self.sam_box_start.x(), self.sam_box_current.x()),
                                          min(self.sam_box_start.y(), self.sam_box_current.y()))
                br = self.image_to_widget(max(self.sam_box_start.x(), self.sam_box_current.x()),
                                          max(self.sam_box_start.y(), self.sam_box_current.y()))
                painter.setPen(QPen(SAM_BOX_COLOR, 2, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(QRectF(tl, br))

            if self.sam_preview_polygon:
                pts = [self.image_to_widget(x, y) for x, y in self.sam_preview_polygon]
                poly = QPolygonF(pts)
                fill = QColor(SAM_PREVIEW_COLOR)
                fill.setAlpha(85)
                painter.setBrush(fill)
                painter.setPen(QPen(SAM_PREVIEW_COLOR, 2))
                painter.drawPolygon(poly)

            for (px, py), label in zip(self.sam_points, self.sam_labels):
                wp = self.image_to_widget(px, py)
                color = SAM_POS_POINT_COLOR if label == 1 else SAM_NEG_POINT_COLOR
                painter.setBrush(color)
                painter.setPen(QPen(QColor("#0b0f16"), 2))
                painter.drawEllipse(wp, 7, 7)

        if self.user_zoom > 1.001:
            painter.setPen(QColor("#9ca3af"))
            painter.drawText(QRectF(8, 8, 220, 20), Qt.AlignLeft, f"缩放 {self.user_zoom:.2f}×")
        if self.mode == "polygon":
            painter.setPen(QColor("#9ca3af"))
            painter.drawText(QRectF(8, self.height() - 24, 420, 20), Qt.AlignLeft,
                             "分割模式：左键加点，右键 / 回车 / 双击 完成，Ctrl+Z 撤销点")
        if self.mode == "defect":
            painter.setPen(QColor("#cbd5e1"))
            shape_text = DEFECT_KIND_LABELS.get(self.current_defect_kind, self.current_defect_kind)
            painter.drawText(
                QRectF(8, self.height() - 42, 720, 20),
                Qt.AlignLeft,
                f"缺陷模式 · 形状：{shape_text}  先选中目标，再在目标内部画缺陷",
            )
            parent = self.selected_parent_for_defect()
            if parent < 0:
                painter.setPen(QColor("#ffd166"))
                painter.drawText(QRectF(8, self.height() - 22, 520, 20), Qt.AlignLeft, "请选择一个目标实例后再标注缺陷")
        if self.mode == "sam":
            painter.setPen(QColor("#22c55e"))
            status = "推理中…" if self.sam_busy else "左键拉框 · Shift+左键 正点 · 右键 负点 · 回车 接受 · Esc 取消"
            painter.drawText(QRectF(8, self.height() - 24, 720, 20), Qt.AlignLeft, f"SAM 模式  {status}")

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
    batch_mode: str = "skip"
    dedup_iou: float = 0.85


def annotation_iou(a: Annotation, b: Annotation) -> float:
    ax1, ay1, ax2, ay2 = a.rect().left(), a.rect().top(), a.rect().right(), a.rect().bottom()
    bx1, by1, bx2, by2 = b.rect().left(), b.rect().top(), b.rect().right(), b.rect().bottom()
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def merge_annotations(existing: list[Annotation], predicted: list[Annotation], threshold: float) -> list[Annotation]:
    merged = [ann.copy() for ann in existing]
    for candidate in predicted:
        if any(candidate.cls == item.cls and annotation_iou(candidate, item) > threshold for item in merged):
            continue
        merged.append(candidate)
    return merged


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
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

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
                if self.cancelled:
                    self.done.emit({"cancelled": True, "completed": idx - 1, "total": len(self.image_paths), "annotations": total})
                    return
                try:
                    frame = load_image(src)
                except Exception as exc:
                    self.progress.emit(idx, len(self.image_paths), f"跳过损坏 {src.name}：{exc}")
                    continue
                stem = safe_stem(src.stem)
                dst_img = image_dir / f"{stem}.jpg"
                label_path = label_dir / f"{stem}.txt"
                if self.params.batch_mode == "skip" and label_path.exists() and label_path.read_text(encoding="utf-8", errors="ignore").strip():
                    self.progress.emit(idx, len(self.image_paths), f"跳过已有标注 {src.name}")
                    continue
                save_image(dst_img, frame)
                anns = predict_annotations(model, frame, self.params, model_names)
                if self.params.batch_mode == "merge":
                    existing = read_labels_file(label_path, frame.shape[1], frame.shape[0])
                    anns = merge_annotations(existing, anns, self.params.dedup_iou)
                write_labels_file(label_path, anns, frame.shape[1], frame.shape[0])
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
                        move_dataset_item_to_trash(image_path, self.output_root)
                        deleted += 1
                    except OSError as exc:
                        self.progress.emit(idx, total, f"移入回收站失败 {image_path.name}：{exc}")
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
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

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
                if self.cancelled:
                    self.done.emit({"cancelled": True, "frames": total_frames, "annotations": total_anns, "output": str(self.output_root)})
                    return
                cap = cv2.VideoCapture(str(video))
                if not cap.isOpened():
                    self.progress.emit(video_idx, total_jobs, f"跳过：{video.name}")
                    continue
                frame_idx = 0
                saved = 0
                while True:
                    if self.cancelled:
                        cap.release()
                        self.done.emit({"cancelled": True, "frames": total_frames, "annotations": total_anns, "output": str(self.output_root)})
                        return
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
        self.setWindowTitle("CVDS AI 辅助 YOLO 标注工具 v2.3")
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
        self.dirty = False
        self.last_error_report = ""
        # v2.2 history
        self.history = HistoryManager()
        self._suspend_history = False  # 切图、undo/redo 自身时不要 push
        # v2.2 SAM
        self.sam_controller: SamController | None = None

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
        # v2.2: history pre-edit
        self.canvas.pre_edit.connect(self.on_pre_edit)
        # v2.2: SAM 信号
        self.canvas.sam_box_committed.connect(self.on_sam_box_committed)
        self.canvas.sam_point_added.connect(self.on_sam_point_added)
        self.canvas.sam_accept_requested.connect(self.on_sam_accept_requested)
        self.canvas.sam_accept_defect_requested.connect(self.on_sam_accept_defect_requested)
        self.canvas.sam_cancel_requested.connect(self.on_sam_cancel_requested)

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

        self.update_status_bar()
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
        self.mode_combo.addItems(["检测框 (detect)", "目标分割 (segment)", "目标内缺陷", SAM_MODE_NAME])
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
        # v2.2: 缺陷形状
        self.defect_kind_combo = QComboBox()
        for kind in DEFECT_KINDS:
            self.defect_kind_combo.addItem(DEFECT_KIND_LABELS[kind], kind)
        self.defect_note_edit = QLineEdit()
        self.defect_note_edit.setPlaceholderText("可选备注，例如贯穿/疑似/边缘缺口")
        self.defect_type_combo.currentIndexChanged.connect(self.update_defect_meta)
        self.defect_severity_combo.currentIndexChanged.connect(self.update_defect_meta)
        self.defect_kind_combo.currentIndexChanged.connect(self.update_defect_meta)
        self.defect_note_edit.textChanged.connect(self.update_defect_meta)
        defect_form.addRow("类型", self.defect_type_combo)
        defect_form.addRow("程度", self.defect_severity_combo)
        defect_form.addRow("形状", self.defect_kind_combo)
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
        self.device_combo.addItems(["自动", "CPU", "GPU"])
        self.device_combo.currentIndexChanged.connect(self.update_status_bar)
        self.ai_mode_combo = QComboBox()
        self.ai_mode_combo.addItem("跳过已有标注图片", "skip")
        self.ai_mode_combo.addItem("覆盖已有标注图片", "overwrite")
        self.ai_mode_combo.addItem("合并到已有标注", "merge")
        self.ai_after_current_check = QCheckBox("仅处理当前图片之后")
        ai_form.addRow("置信度", self.conf_spin)
        ai_form.addRow("输入尺寸", self.imgsz_spin)
        ai_form.addRow("设备", self.device_combo)
        ai_form.addRow("批量模式", self.ai_mode_combo)
        ai_form.addRow("", self.ai_after_current_check)

        # v2.2: SAM 半自动分割配置
        sam_box = QGroupBox("SAM 半自动分割")
        sam_layout = QVBoxLayout(sam_box)
        sam_path_row = QHBoxLayout()
        self.sam_weights_edit = QLineEdit(DEFAULT_SAM_WEIGHTS)
        sam_pick_btn = QPushButton("选择")
        sam_pick_btn.setMinimumWidth(58)
        sam_pick_btn.clicked.connect(self.pick_sam_weights)
        sam_path_row.addWidget(QLabel("SAM 权重"))
        sam_path_row.addWidget(self.sam_weights_edit, 1)
        sam_path_row.addWidget(sam_pick_btn)
        sam_layout.addLayout(sam_path_row)
        sam_preset_row = QHBoxLayout()
        for label, fname in SAM_PRESETS:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, f=fname: self.sam_weights_edit.setText(f))
            sam_preset_row.addWidget(btn)
        sam_layout.addLayout(sam_preset_row)
        sam_action_row = QHBoxLayout()
        self.sam_load_btn = QPushButton("加载 / 重载 SAM")
        self.sam_load_btn.clicked.connect(self.reload_sam_controller)
        self.sam_status_label = QLabel("未加载")
        self.sam_status_label.setStyleSheet("color:#9ca3af;")
        sam_action_row.addWidget(self.sam_load_btn)
        sam_action_row.addWidget(self.sam_status_label, 1)
        sam_layout.addLayout(sam_action_row)
        sam_hint = QLabel(
            "Alt+S 进入；左键拉框 → 预览 mask；Shift+左键 加正点；右键 加负点；"
            "回车 接受；Esc 取消"
        )
        sam_hint.setWordWrap(True)
        sam_hint.setStyleSheet("color:#9ca3af; font-size:11px;")
        sam_layout.addWidget(sam_hint)

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
        self.cancel_worker_btn = QPushButton("取消任务")
        self.cancel_worker_btn.clicked.connect(self.cancel_current_worker)
        self.cancel_worker_btn.setEnabled(False)
        op_grid.addWidget(self.scan_btn, 0, 0)
        op_grid.addWidget(self.ai_btn, 0, 1)
        op_grid.addWidget(self.extract_btn, 1, 0)
        op_grid.addWidget(self.extract_ai_btn, 1, 1)
        op_grid.addWidget(self.save_btn, 2, 0)
        op_grid.addWidget(self.delete_btn, 2, 1)
        op_grid.addWidget(self.cancel_worker_btn, 3, 0, 1, 2)

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

        # v2.3 数据与环境工具
        tool_box = QGroupBox("v2.3 工具")
        tool_grid = QGridLayout(tool_box)
        self.diagnose_btn = QPushButton("环境自检")
        self.diagnose_btn.clicked.connect(self.run_environment_diagnose)
        self.quality_btn = QPushButton("数据集质检")
        self.quality_btn.clicked.connect(self.run_dataset_quality)
        self.export_btn = QPushButton("导出数据集")
        self.export_btn.clicked.connect(self.run_dataset_export)
        self.trash_btn = QPushButton("打开回收站")
        self.trash_btn.clicked.connect(self.open_trash_dir)
        self.error_report_btn = QPushButton("复制错误报告")
        self.error_report_btn.clicked.connect(self.copy_error_report)
        self.shortcut_btn = QPushButton("快捷键帮助 (F1)")
        self.shortcut_btn.clicked.connect(self.show_shortcut_help)
        tool_grid.addWidget(self.diagnose_btn, 0, 0)
        tool_grid.addWidget(self.quality_btn, 0, 1)
        tool_grid.addWidget(self.export_btn, 1, 0)
        tool_grid.addWidget(self.trash_btn, 1, 1)
        tool_grid.addWidget(self.error_report_btn, 2, 0)
        tool_grid.addWidget(self.shortcut_btn, 2, 1)

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
        layout.addWidget(sam_box)
        layout.addWidget(video_box)
        layout.addWidget(op_box)
        layout.addWidget(manual_box)
        layout.addWidget(tool_box)
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
        self.defect_table.setHorizontalHeaderLabels(["目标#", "缺陷", "程度", "形状/几何", "备注", "ID"])
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

    def current_device_value(self) -> str:
        text = self.device_combo.currentText() if hasattr(self, "device_combo") else "自动"
        diagnose = diagnose_environment(self.weights_edit.text() if hasattr(self, "weights_edit") else None, self.sam_weights_edit.text() if hasattr(self, "sam_weights_edit") else None)
        if text == "自动":
            device = "0" if diagnose.cuda_available else "cpu"
            self.append_log(f"自动设备选择：实际使用 {'GPU' if device == '0' else 'CPU'}")
            return device
        if text == "GPU":
            if not diagnose.cuda_available:
                raise RuntimeError("当前电脑未检测到可用 NVIDIA CUDA 推理环境，请改用 CPU 或安装匹配的 GPU 运行环境。")
            return "0"
        return "cpu"

    def update_status_bar(self) -> None:
        index_text = f"{self.current_index + 1}/{len(self.image_paths)}" if self.current_index >= 0 else "未加载"
        mode_text = self.mode_combo.currentText() if hasattr(self, "mode_combo") else "-"
        class_text = self.class_combo.currentText() if hasattr(self, "class_combo") else "-"
        target_count = len(self.canvas.annotations) if hasattr(self, "canvas") else 0
        defect_count = len(self.canvas.defects) if hasattr(self, "canvas") else 0
        save_text = "未保存" if self.dirty else "已保存"
        device_text = self.device_combo.currentText() if hasattr(self, "device_combo") else "自动"
        self.statusBar().showMessage(
            f"{index_text} | 模式:{mode_text} | 类别:{class_text} | 目标:{target_count} | 缺陷:{defect_count} | {save_text} | 设备:{device_text}"
        )

    def set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self.update_status_bar()

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
            # v2.2: Undo/Redo
            ("Ctrl+Z", self.undo),
            ("Ctrl+Y", self.redo),
            ("Ctrl+Shift+Z", self.redo),
            ("F1", self.show_shortcut_help),
        ]
        guarded_bindings = [
            ("A", lambda: self.step_image(-1)),
            ("D", lambda: self.step_image(1)),
            ("Esc", self.canvas.rollback_current_action),
            ("Alt+B", lambda: self.mode_combo.setCurrentIndex(0)),
            ("Alt+P", lambda: self.mode_combo.setCurrentIndex(1)),
            ("Alt+X", lambda: self.mode_combo.setCurrentIndex(2)),
            ("Alt+S", lambda: self.mode_combo.setCurrentIndex(3)),  # v2.2: SAM
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
        kind = self.defect_kind_combo.currentData() or "polygon"
        note = self.defect_note_edit.text()
        self.canvas.set_defect_meta(defect_type, severity, note, kind=kind)
        idx = self.canvas.selected_defect
        if 0 <= idx < len(self.canvas.defects):
            # 修改选中缺陷的元数据（type/severity/note），但不改 kind——
            # kind 与几何形状强绑定，修改 kind 需要重画
            self.canvas.pre_edit.emit()
            defect = self.canvas.defects[idx]
            defect.defect_type = defect_type if defect_type in DEFECT_TYPES else "other"
            defect.severity = severity if severity in DEFECT_SEVERITIES else "medium"
            defect.note = note.strip()
            self.canvas.defects_changed.emit()
            self.canvas.update()

    def current_task(self) -> str:
        # v2.2: detect 模式才是 detect，其他都按 segment 写
        return "detect" if self.mode_combo.currentIndex() == 0 else "segment"

    def on_mode_changed(self, idx: int) -> None:
        if idx == 0:
            mode = "box"
        elif idx == 1:
            mode = "polygon"
        elif idx == 2:
            mode = "defect"
        else:
            mode = "sam"
        self.canvas.set_mode(mode)
        # v2.2: 进入 SAM 模式时确保 controller 已初始化并同步当前图
        if mode == "sam":
            if not self.ensure_sam_controller():
                self.mode_combo.blockSignals(True)
                self.mode_combo.setCurrentIndex(1)
                self.mode_combo.blockSignals(False)
                self.canvas.set_mode("polygon")
                QMessageBox.information(self, "SAM 未加载", "请先加载可用的 SAM 权重，再进入 SAM 半自动分割模式。")
                return
            if self.sam_controller is not None and self.current_frame is not None and self.current_index >= 0:
                self.sam_controller.set_image(
                    self.current_frame,
                    str(self.image_paths[self.current_index]),
                )
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

    # -------------------- v2.2 Undo / Redo --------------------

    def on_pre_edit(self) -> None:
        """canvas 即将编辑：把当前状态推入 undo 栈。"""
        if self._suspend_history:
            return
        self.history.push(CanvasSnapshot.capture(self.canvas))
        self.set_dirty(True)

    def undo(self) -> None:
        if not self.history.can_undo():
            self.append_log("没有可撤销的操作")
            return
        current = CanvasSnapshot.capture(self.canvas)
        target = self.history.undo(current)
        if target is None:
            return
        self._apply_snapshot_silently(target)
        self.set_dirty(True)
        self.append_log(f"撤销  (undo {len(self.history.undo_stack)} / redo {len(self.history.redo_stack)})")

    def redo(self) -> None:
        if not self.history.can_redo():
            self.append_log("没有可重做的操作")
            return
        current = CanvasSnapshot.capture(self.canvas)
        target = self.history.redo(current)
        if target is None:
            return
        self._apply_snapshot_silently(target)
        self.set_dirty(True)
        self.append_log(f"重做  (undo {len(self.history.undo_stack)} / redo {len(self.history.redo_stack)})")

    def _apply_snapshot_silently(self, snapshot: CanvasSnapshot) -> None:
        """把快照应用到 canvas，期间屏蔽 pre_edit 防止无限循环。"""
        self._suspend_history = True
        try:
            snapshot.apply_to(self.canvas)
            # 用 emit 通知 UI 同步表格、列表计数
            self.canvas.annotations_changed.emit()
            self.canvas.defects_changed.emit()
            self.canvas.selection_changed.emit(self.canvas.selected)
            self.canvas.defect_selection_changed.emit(self.canvas.selected_defect)
            self.canvas.update()
        finally:
            self._suspend_history = False

    # -------------------- v2.2 SAM --------------------

    def pick_sam_weights(self) -> None:
        existing = Path(self.sam_weights_edit.text())
        start = str(existing.parent if existing.exists() else (ROOT / "weights"))
        path, _ = QFileDialog.getOpenFileName(self, "选择 SAM 权重", start, "PyTorch (*.pt)")
        if path:
            self.sam_weights_edit.setText(path)

    def ensure_sam_controller(self) -> bool:
        if self.sam_controller is not None:
            return True
        return self.reload_sam_controller()

    def reload_sam_controller(self) -> bool:
        # 重载前关闭旧的
        if self.sam_controller is not None:
            try:
                self.sam_controller.shutdown()
            except Exception:  # noqa: BLE001
                pass
            self.sam_controller = None
        weights = self.sam_weights_edit.text().strip()
        if not weights:
            QMessageBox.warning(self, "未配置 SAM 权重", "请先在 SAM 区域配置权重文件")
            self.sam_status_label.setText("未加载")
            return False
        diagnose = diagnose_environment(self.weights_edit.text(), weights)
        if not diagnose.sam_available:
            message = "当前发布包未包含 SAM 半自动分割环境，基础手工标注功能仍可正常使用。"
            if diagnose.sam_error:
                message += "\n\n" + diagnose.sam_error
            self.append_log("SAM 不可用：" + message)
            QMessageBox.warning(self, "SAM 不可用", message)
            self.sam_status_label.setText("SAM 不可用")
            return False
        # 验证文件存在(允许 ultralytics 自动下载的官方名)
        wpath = Path(weights)
        official_prefixes = ("mobile_sam", "sam2", "sam_b", "sam_l", "sam_h", "FastSAM")
        if not wpath.exists() and not any(wpath.name.lower().startswith(p.lower()) for p in official_prefixes):
            reply = QMessageBox.question(
                self, "权重文件不存在",
                f"找不到 {weights}\n\n如果是官方权重名 (例如 mobile_sam.pt),ultralytics 会自动下载。\n是否继续?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.sam_status_label.setText("未加载")
                return False
        self.sam_status_label.setText("加载中…")
        try:
            device = self.current_device_value()
        except RuntimeError as exc:
            QMessageBox.warning(self, "CUDA 不可用", str(exc))
            self.sam_status_label.setText("未加载")
            return False
        try:
            self.sam_controller = SamController(weights, device, parent=self)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "SAM 初始化失败", str(exc))
            self.sam_status_label.setText("加载失败")
            return False
        self.sam_controller.mask_ready.connect(self.on_sam_mask_ready)
        self.sam_controller.failed.connect(self.on_sam_failed)
        self.sam_controller.busy_changed.connect(self.on_sam_busy_changed)
        self.sam_status_label.setText(f"已加载: {Path(weights).name}")
        self.append_log(f"SAM 已加载: {weights} @ {device}")
        # 如果当前已有图片，同步给 SAM
        if self.current_frame is not None and self.current_index >= 0:
            self.sam_controller.set_image(
                self.current_frame,
                str(self.image_paths[self.current_index]),
            )
        return True

    def on_sam_box_committed(self, x1: float, y1: float, x2: float, y2: float) -> None:
        if not self.ensure_sam_controller() or self.sam_controller is None:
            return
        image_id = str(self.image_paths[self.current_index]) if self.current_index >= 0 else ""
        self.sam_controller.submit(SamRequest(kind="box", bbox=(x1, y1, x2, y2), image_id=image_id))

    def on_sam_point_added(self, x: float, y: float, label: int) -> None:
        if not self.ensure_sam_controller() or self.sam_controller is None:
            return
        if not self.canvas.sam_points:
            return
        image_id = str(self.image_paths[self.current_index]) if self.current_index >= 0 else ""
        self.sam_controller.submit(SamRequest(
            kind="points",
            points=list(self.canvas.sam_points),
            labels=list(self.canvas.sam_labels),
            image_id=image_id,
        ))

    def on_sam_accept_requested(self) -> None:
        if self.canvas.sam_preview_polygon is None:
            return
        ok = self.canvas.sam_accept(as_defect=False)
        if ok:
            n = len(self.canvas.sam_preview_polygon) if self.canvas.sam_preview_polygon else 0
            self.append_log(f"SAM 已添加分割标注 ({n} 顶点)")

    def on_sam_accept_defect_requested(self) -> None:
        if self.canvas.sam_preview_polygon is None:
            return
        ok = self.canvas.sam_accept(parent_index=self.canvas.selected, as_defect=True)
        if ok:
            self.append_log("SAM 已添加为当前目标缺陷 polygon")

    def on_sam_cancel_requested(self) -> None:
        # canvas 已自行清空 preview / points / labels
        pass

    def on_sam_mask_ready(self, polygon, image_id: str) -> None:
        cur_id = str(self.image_paths[self.current_index]) if self.current_index >= 0 else ""
        if image_id and image_id != cur_id:
            return
        self.canvas.sam_set_preview(polygon)

    def on_sam_failed(self, msg: str) -> None:
        first_line = msg.splitlines()[0] if msg else "(空)"
        self.last_error_report = msg
        self.append_log(f"SAM 错误: {first_line}\n{msg}")

    def on_sam_busy_changed(self, busy: bool) -> None:
        self.canvas.sam_set_busy(busy)
        if hasattr(self, "sam_status_label"):
            if busy:
                self.sam_status_label.setText("推理中…")
            elif self.sam_controller is not None:
                self.sam_status_label.setText(f"已加载: {Path(self.sam_weights_edit.text()).name}")

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

    def cancel_current_worker(self) -> None:
        if self.worker is not None and hasattr(self.worker, "cancel"):
            self.worker.cancel()
            self.append_log("正在取消任务，已完成的结果会保留。")

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
            if not self.save_current(silent=True):
                if self.current_index >= 0:
                    old_idx = self.image_model.index(self.current_index, 0)
                    QTimer.singleShot(0, lambda: self.image_list.setCurrentIndex(old_idx))
                return
        # v2.2: 切图前清空当前图片的 history
        self.history.clear()
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
        # v2.2: 加载新图片的标注，不应该入 history（这不是用户的编辑动作）
        self._suspend_history = True
        try:
            self.canvas.set_image(frame)
            self.canvas.set_labels(self.labels())
            self.canvas.set_annotations(anns)
            self.canvas.set_defects(defects)
        finally:
            self._suspend_history = False
        self.info_label.setText(
            f"{row + 1}/{len(self.image_paths)}  {path.name}  {w}×{h}  目标:{len(anns)}  缺陷:{len(self.canvas.defects)}"
        )
        self.image_model.update_box_count(row, len(anns))
        self.sync_full_count(path, len(anns))
        self.refresh_box_table()
        self.set_dirty(False)
        # v2.2: SAM controller 同步当前帧
        if self.sam_controller is not None:
            self.sam_controller.set_image(frame, str(path))
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
        lower_text = text.lower()
        if lower_text == "empty":
            for i in range(len(self.image_paths)):
                if self.image_model.box_count(i) == 0:
                    self.goto_index(i)
                    self.jump_edit.clear()
                    self.canvas.setFocus()
                    return
        if lower_text.startswith("cls:"):
            name = lower_text[4:].strip()
            labels = [label.lower() for label in self.labels()]
            target_cls = labels.index(name) if name in labels else None
            if target_cls is not None:
                for i, path in enumerate(self.image_paths):
                    try:
                        frame = load_image(path)
                        h, w = frame.shape[:2]
                        anns = read_labels_file(self.label_path_for_image(path), w, h)
                    except Exception:
                        continue
                    if any(ann.cls == target_cls for ann in anns):
                        self.goto_index(i)
                        self.jump_edit.clear()
                        self.canvas.setFocus()
                        return
        if lower_text.startswith("defect:"):
            defect_type = lower_text[7:].strip()
            for i, path in enumerate(self.image_paths):
                defect_path = self.defect_path_for_image(path)
                if defect_path.exists() and defect_type in defect_path.read_text(encoding="utf-8", errors="ignore").lower():
                    self.goto_index(i)
                    self.jump_edit.clear()
                    self.canvas.setFocus()
                    return
        for i, path in enumerate(self.image_paths):
            if lower_text in path.name.lower():
                self.goto_index(i)
                self.jump_edit.clear()
                self.canvas.setFocus()
                return
        QMessageBox.information(self, "未找到", f"没有匹配的图片：{text}")

    # -------------------- 保存 / 表格 --------------------

    def save_current(self, silent: bool = False) -> bool:
        if self.current_index < 0 or self.current_frame is None:
            return True
        path = self.image_paths[self.current_index]
        dst_img = self.output_image_path(path)
        if path.resolve() != dst_img.resolve():
            try:
                save_image(dst_img, self.current_frame)
            except Exception as exc:
                self.last_error_report = traceback.format_exc()
                self.append_log(f"图片保存失败：{exc}")
                QMessageBox.warning(self, "保存失败", "标注保存失败，已阻止切换图片，请检查输出目录权限。\n\n" + str(exc))
                return False
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
            self.last_error_report = traceback.format_exc()
            self.append_log(f"标注写入失败：{exc}")
            QMessageBox.warning(self, "保存失败", "标注保存失败，已阻止切换图片，请检查输出目录权限。\n\n" + str(exc))
            return False
        self.image_model.update_box_count(self.current_index, len(self.canvas.annotations))
        self.sync_full_count(self.image_paths[self.current_index], len(self.canvas.annotations))
        self.set_dirty(False)
        if not silent:
            self.append_log(f"已保存：{label_path}")
        return True

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
            kind_name = DEFECT_KIND_LABELS.get(defect.kind, defect.kind)
            # v2.2: 第 4 列改为显示形状 + 几何摘要
            if defect.is_point:
                geom = f"{kind_name}@({defect.points[0][0]:.0f},{defect.points[0][1]:.0f})"
            elif defect.is_box:
                r = defect.rect()
                geom = f"{kind_name} {r.width():.0f}×{r.height():.0f}"
            else:
                geom = f"{kind_name} {len(defect.points)}点"
            values = [
                str(defect.parent_index + 1),
                type_name,
                severity_name,
                geom,
                defect.note,
                defect.defect_id,
            ]
            for col, value in enumerate(values):
                self.defect_table.setItem(row, col, QTableWidgetItem(str(value)))

    def on_annotations_changed(self) -> None:
        self.refresh_box_table()
        self.update_status_bar()

    def on_defects_changed(self) -> None:
        self.refresh_box_table()
        self.update_status_bar()

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
            # 选中缺陷时同步面板控件；用 block + 一起恢复 avoid 触发 update_defect_meta 改写选中缺陷
            self.defect_type_combo.blockSignals(True)
            self.defect_severity_combo.blockSignals(True)
            self.defect_kind_combo.blockSignals(True)
            self.defect_note_edit.blockSignals(True)
            try:
                type_index = self.defect_type_combo.findData(defect.defect_type)
                if type_index >= 0:
                    self.defect_type_combo.setCurrentIndex(type_index)
                severity_index = self.defect_severity_combo.findData(defect.severity)
                if severity_index >= 0:
                    self.defect_severity_combo.setCurrentIndex(severity_index)
                kind_index = self.defect_kind_combo.findData(defect.kind)
                if kind_index >= 0:
                    self.defect_kind_combo.setCurrentIndex(kind_index)
                self.defect_note_edit.setText(defect.note)
            finally:
                self.defect_type_combo.blockSignals(False)
                self.defect_severity_combo.blockSignals(False)
                self.defect_kind_combo.blockSignals(False)
                self.defect_note_edit.blockSignals(False)
            # 把这些值同步到 canvas 的 "当前缺陷元数据" 上(不修改已有缺陷)
            self.canvas.set_defect_meta(
                defect.defect_type, defect.severity, defect.note, kind=defect.kind,
            )
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
        if self.save_current():
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
        copied_defects: list[DefectAnnotation] = []
        for defect in prev_defects:
            if not (0 <= defect.parent_index < len(copied)):
                continue
            copied_defect = defect.copy()  # 包含 kind 字段
            copied_defect.defect_id = uuid.uuid4().hex[:12]
            copied_defect.points = [(x * sx, y * sy) for x, y in defect.points]
            copied_defect.parent_cls = copied[copied_defect.parent_index].cls
            copied_defect.created_at = datetime.now().isoformat(timespec="seconds")
            copied_defects.append(copied_defect)
        # v2.2: 让 undo 能回到 copy 之前
        self.canvas.pre_edit.emit()
        self._suspend_history = True
        try:
            self.canvas.set_annotations(copied)
            self.canvas.set_defects(copied_defects)
        finally:
            self._suspend_history = False
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
        if not self.save_current(silent=True):
            return
        image_path = self.image_paths[self.current_index]
        in_output = self.is_output_image_path(image_path)
        msg = f"确定删除当前图片？\n{image_path.name}"
        if in_output:
            msg += "\n\n图片、标签和缺陷文件将移动到 .trash 回收站。"
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
                trash_dir = move_dataset_item_to_trash(image_path, self.output_root())
                self.append_log(f"已移入回收站：{trash_dir}")
            except OSError as exc:
                self.append_log(f"移入回收站失败：{exc}")
                QMessageBox.warning(self, "删除失败", f"无法移动到回收站：{exc}")
                return
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
            device=self.current_device_value(),
            output_root=self.output_root(),
            task=self.current_task(),
            batch_mode=str(self.ai_mode_combo.currentData() or "skip"),
        )

    def ai_label_images(self) -> None:
        image_paths = list(self.image_paths)
        if self.ai_after_current_check.isChecked() and self.current_index >= 0:
            image_paths = image_paths[self.current_index:]
        if not image_paths:
            QMessageBox.warning(self, "没有图片", "请先点击\"加载图片\"，再批量标注")
            return
        if not Path(self.weights_edit.text()).exists():
            QMessageBox.warning(self, "权重不存在", f"找不到模型权重：{self.weights_edit.text()}")
            return
        try:
            params = self.ai_params()
        except RuntimeError as exc:
            QMessageBox.warning(self, "CUDA 不可用", str(exc))
            return
        self.start_worker(ImageAutoLabelWorker(image_paths, params), self.scan_output_images)

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
        try:
            params = self.ai_params() if do_ai else None
        except RuntimeError as exc:
            QMessageBox.warning(self, "CUDA 不可用", str(exc))
            return
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
        self.cancel_worker_btn.setEnabled(False)
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
            self.delete_empty_btn, self.load_yolo_btn, self.diagnose_btn,
            self.quality_btn, self.export_btn, self.trash_btn, self.error_report_btn,
        ]:
            widget.setEnabled(enabled)
        self.cancel_worker_btn.setEnabled(not enabled)

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text)
        try:
            RUNTIME_PATHS.logs_dir.mkdir(parents=True, exist_ok=True)
            log_path = RUNTIME_PATHS.logs_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(datetime.now().strftime("%H:%M:%S ") + text + "\n")
        except OSError:
            pass

    def run_environment_diagnose(self) -> None:
        result = diagnose_environment(self.weights_edit.text(), self.sam_weights_edit.text())
        self.append_log("环境自检：\n" + result.to_json())
        if result.ultralytics_available and result.torch_available:
            self.ai_btn.setEnabled(True)
            self.extract_ai_btn.setEnabled(True)
            self.sam_load_btn.setEnabled(True)
        else:
            self.ai_btn.setEnabled(False)
            self.extract_ai_btn.setEnabled(False)
            self.sam_load_btn.setEnabled(False)
            self.append_log("当前发布包未包含 AI 自动标注环境，基础手工标注功能仍可正常使用。")

    def run_dataset_quality(self) -> None:
        try:
            report = audit_dataset(self.output_root())
        except Exception as exc:
            self.last_error_report = traceback.format_exc()
            QMessageBox.warning(self, "质检失败", str(exc))
            self.append_log("数据集质检失败：" + str(exc))
            return
        self.append_log(
            "数据集质检完成："
            f"图片 {report.total_images}，标签 {report.total_labels}，空标签 {report.empty_label_images}，"
            f"缺失标签 {report.missing_labels}，孤儿标签 {report.orphan_labels}，异常缺陷 {report.invalid_defects}。"
        )
        self.append_log(f"质检报告：{report.report_json}")
        QMessageBox.information(self, "数据集质检完成", f"报告已保存：\n{report.report_json}")

    def run_dataset_export(self) -> None:
        target = QFileDialog.getExistingDirectory(self, "选择导出目录", str(RUNTIME_PATHS.user_data_dir))
        if not target:
            return
        try:
            result = export_dataset(self.output_root(), Path(target), val_ratio=0.2, include_empty=True, make_zip=True)
        except Exception as exc:
            self.last_error_report = traceback.format_exc()
            QMessageBox.warning(self, "导出失败", str(exc))
            self.append_log("数据集导出失败：" + str(exc))
            return
        self.append_log(f"数据集导出完成：train={result.train_count}, val={result.val_count}, path={result.output_dir}")
        if result.zip_path:
            self.append_log(f"ZIP：{result.zip_path}")

    def open_trash_dir(self) -> None:
        trash = self.output_root() / ".trash"
        trash.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(trash))
        except OSError as exc:
            QMessageBox.warning(self, "打开失败", str(exc))

    def copy_error_report(self) -> None:
        diagnose = diagnose_environment(self.weights_edit.text(), self.sam_weights_edit.text()).to_json()
        recent_logs = self.log.toPlainText().splitlines()[-80:]
        report = (
            f"app version: {APP_VERSION}\n"
            f"python: {sys.version}\n"
            f"platform: {sys.platform}\n"
            f"frozen: {bool(getattr(sys, 'frozen', False))}\n"
            f"diagnose:\n{diagnose}\n"
            f"recent logs:\n" + "\n".join(recent_logs) + "\n"
            f"traceback:\n{self.last_error_report}"
        )
        QApplication.clipboard().setText(report)
        self.append_log("错误报告已复制到剪贴板。")

    def show_shortcut_help(self) -> None:
        QMessageBox.information(
            self,
            "快捷键帮助",
            "Ctrl+S 保存\nCtrl+Shift+S 保存并下一张\nA/D 上一张/下一张\n"
            "Alt+B 检测框\nAlt+P 目标分割\nAlt+X 缺陷层\nAlt+S SAM\n"
            "Ctrl+Z 撤销\nCtrl+Y 重做\nDelete 删除选中\nEsc 撤回当前动作\n"
            "Enter 接受 SAM 为目标，Ctrl+Enter 接受 SAM 为缺陷。",
        )

    # -------------------- 设置持久化 --------------------

    def restore_settings(self) -> None:
        s = self.settings
        for key, edit in [
            ("paths/weights", self.weights_edit),
            ("paths/image_folder", self.image_folder_edit),
            ("paths/video_folder", self.video_folder_edit),
            ("paths/output", self.output_edit),
            ("paths/sam_weights", self.sam_weights_edit),  # v2.2
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
        device_text = str(device)
        if device_text == "0":
            device_text = "GPU"
        elif device_text.lower() == "cpu":
            device_text = "CPU"
        if device_text and self.device_combo.findText(device_text) >= 0:
            self.device_combo.setCurrentText(device_text)
        try:
            restored_mode = int(s.value("ui/mode", 0))
            self.mode_combo.setCurrentIndex(restored_mode)
        except (TypeError, ValueError):
            restored_mode = self.mode_combo.currentIndex()
        # v2.2: 缺陷形状
        defect_kind = s.value("ui/defect_kind", "polygon")
        kind_idx = self.defect_kind_combo.findData(str(defect_kind))
        if kind_idx >= 0:
            self.defect_kind_combo.setCurrentIndex(kind_idx)
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
        s.setValue("paths/sam_weights", self.sam_weights_edit.text())  # v2.2
        s.setValue("ai/conf", float(self.conf_spin.value()))
        s.setValue("ai/imgsz", int(self.imgsz_spin.value()))
        s.setValue("ai/device", self.device_combo.currentText())
        s.setValue("video/step", int(self.frame_step_spin.value()))
        s.setValue("video/max_frames", int(self.max_frames_spin.value()))
        s.setValue("ui/mode", int(self.mode_combo.currentIndex()))
        s.setValue("ui/defect_kind", self.defect_kind_combo.currentData() or "polygon")  # v2.2
        s.setValue("ui/geometry", self.saveGeometry())
        s.setValue("ui/splitter", self.splitter.sizes())
        s.setValue("ui/last_image_index", self.current_index if self.current_index >= 0 else 0)

    def closeEvent(self, event) -> None:
        if not self.save_current(silent=True):
            event.ignore()
            return
        # v2.2: 关闭 SAM 工作线程
        if self.sam_controller is not None:
            try:
                self.sam_controller.shutdown()
            except Exception:
                pass
            self.sam_controller = None
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
        print("v2.3 window ok")
        return 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
