import json
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml
from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, QPoint, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
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
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ultralytics import YOLO


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


def find_project_root() -> Path:
    if os.environ.get("CVDS_ROOT"):
        return Path(os.environ["CVDS_ROOT"]).resolve()
    start = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    for candidate in [start, *start.parents]:
        if (candidate / "weights").exists() or (candidate / "datasets").exists():
            return candidate
    return start


ROOT = find_project_root()
DEFAULT_WEIGHTS = ROOT / "weights" / "cvds_yolo26n_package_best.pt"
DEFAULT_OUTPUT = ROOT / "datasets" / "cvds_annotation_yolo"
DEFAULT_IMAGE_FOLDER = ROOT / "datasets" / "cvds_crossbelt_annotation_seed" / "images"
DEFAULT_VIDEO_FOLDER = ROOT


@dataclass
class Box:
    cls: int
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float | None = None

    def normalized(self, width: int, height: int) -> str:
        x1 = max(0.0, min(float(width), self.x1))
        y1 = max(0.0, min(float(height), self.y1))
        x2 = max(0.0, min(float(width), self.x2))
        y2 = max(0.0, min(float(height), self.y2))
        left, right = sorted([x1, x2])
        top, bottom = sorted([y1, y2])
        bw = max(0.0, right - left)
        bh = max(0.0, bottom - top)
        cx = left + bw / 2
        cy = top + bh / 2
        return f"{self.cls} {cx / width:.6f} {cy / height:.6f} {bw / width:.6f} {bh / height:.6f}"

    @staticmethod
    def from_yolo(line: str, width: int, height: int) -> "Box | None":
        parts = line.split()
        if len(parts) != 5:
            return None
        cls = int(float(parts[0]))
        x, y, w, h = [float(v) for v in parts[1:]]
        x1 = (x - w / 2) * width
        y1 = (y - h / 2) * height
        x2 = (x + w / 2) * width
        y2 = (y + h / 2) * height
        return Box(cls, x1, y1, x2, y2)

    def rect(self) -> QRectF:
        x1, x2 = sorted([self.x1, self.x2])
        y1, y2 = sorted([self.y1, self.y2])
        return QRectF(x1, y1, x2 - x1, y2 - y1)


def cv_to_qimage(frame: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"图片读取失败：{path}")
    return img


def save_image(path: Path, img: np.ndarray) -> None:
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


def read_labels_file(path: Path, width: int, height: int) -> list[Box]:
    if not path.exists():
        return []
    boxes = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        box = Box.from_yolo(line, width, height)
        if box is not None:
            boxes.append(box)
    return boxes


def write_labels_file(path: Path, boxes: list[Box], width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    valid = []
    for box in boxes:
        rect = box.rect()
        if rect.width() >= 2 and rect.height() >= 2:
            valid.append(box.normalized(width, height))
    path.write_text("\n".join(valid) + ("\n" if valid else ""), encoding="utf-8")


def write_data_yaml(output_root: Path, labels: list[str]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    data = {
        "path": str(output_root).replace("\\", "/"),
        "train": "images/train",
        "val": "images/train",
        "names": {idx: name for idx, name in enumerate(labels)},
    }
    (output_root / "data.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_data_yaml_labels(output_root: Path) -> list[str]:
    data_yaml = output_root / "data.yaml"
    if not data_yaml.exists():
        return []
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    names = data.get("names")
    if isinstance(names, list):
        return [str(name) for name in names]
    if isinstance(names, dict):
        return [str(names[key]) for key in sorted(names, key=lambda item: int(item))]
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


def count_yolo_labels(path: Path) -> int:
    try:
        if not path.exists() or path.stat().st_size == 0:
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())
    except OSError:
        return 0


class ImageListModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.box_counts: list[int | None] = []

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
            prefix = "" if count is None else f"{count}框  "
            return f"{prefix}{path.name}"
        if role == Qt.ToolTipRole:
            return str(path)
        return None

    def set_paths(self, paths: list[Path], box_counts: list[int | None] | None = None) -> None:
        self.beginResetModel()
        self.paths = paths
        self.box_counts = box_counts if box_counts is not None else [None] * len(paths)
        if len(self.box_counts) != len(self.paths):
            self.box_counts = [None] * len(paths)
        self.endResetModel()

    def update_box_count(self, row: int, count: int) -> None:
        if 0 <= row < len(self.box_counts):
            self.box_counts[row] = count
            model_index = self.index(row, 0)
            self.dataChanged.emit(model_index, model_index, [Qt.DisplayRole])

    def box_count(self, row: int) -> int | None:
        if 0 <= row < len(self.box_counts):
            return self.box_counts[row]
        return None

    def remove_row(self, row: int) -> None:
        if 0 <= row < len(self.paths):
            self.beginRemoveRows(QModelIndex(), row, row)
            self.paths.pop(row)
            self.box_counts.pop(row)
            self.endRemoveRows()


class ImageCanvas(QWidget):
    boxes_changed = Signal()
    selection_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(760, 520)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.pixmap: QPixmap | None = None
        self.image_size = (0, 0)
        self.boxes: list[Box] = []
        self.labels: list[str] = ["parcel"]
        self.current_cls = 0
        self.selected = -1
        self.drawing = False
        self.start_image: QPoint | None = None
        self.current_image: QPoint | None = None
        self.drag_mode: str | None = None
        self.drag_start_image: QPoint | None = None
        self.drag_original_box: Box | None = None
        self.resize_handle: str | None = None
        self.drag_changed = False

    def set_image(self, frame: np.ndarray | None) -> None:
        if frame is None:
            self.pixmap = None
            self.image_size = (0, 0)
        else:
            h, w = frame.shape[:2]
            self.image_size = (w, h)
            self.pixmap = QPixmap.fromImage(cv_to_qimage(frame))
        self.selected = -1
        self.update()

    def set_boxes(self, boxes: list[Box]) -> None:
        self.boxes = boxes
        self.selected = -1
        self.update()

    def set_labels(self, labels: list[str]) -> None:
        self.labels = labels or ["parcel"]
        self.update()

    def set_current_cls(self, cls: int) -> None:
        self.current_cls = max(0, cls)

    def image_rect(self) -> QRectF:
        if not self.pixmap:
            return QRectF()
        w, h = self.image_size
        if w <= 0 or h <= 0:
            return QRectF()
        scale = min(self.width() / w, self.height() / h)
        draw_w = w * scale
        draw_h = h * scale
        return QRectF((self.width() - draw_w) / 2, (self.height() - draw_h) / 2, draw_w, draw_h)

    def widget_to_image(self, point: QPoint) -> QPoint | None:
        rect = self.image_rect()
        if rect.isNull() or not rect.contains(point):
            return None
        w, h = self.image_size
        x = int((point.x() - rect.left()) / rect.width() * w)
        y = int((point.y() - rect.top()) / rect.height() * h)
        return QPoint(max(0, min(w, x)), max(0, min(h, y)))

    def image_to_widget_rect(self, box: Box) -> QRectF:
        rect = self.image_rect()
        w, h = self.image_size
        b = box.rect()
        return QRectF(
            rect.left() + b.left() / w * rect.width(),
            rect.top() + b.top() / h * rect.height(),
            b.width() / w * rect.width(),
            b.height() / h * rect.height(),
        )

    def hit_test_box(self, point: QPoint) -> int:
        for idx in range(len(self.boxes) - 1, -1, -1):
            if self.boxes[idx].rect().contains(point):
                return idx
        return -1

    def hit_resize_handle(self, box: Box, point: QPoint) -> str | None:
        w, h = self.image_size
        threshold = max(8, int(min(w, h) * 0.015))
        rect = box.rect()
        corners = {
            "tl": QPoint(int(rect.left()), int(rect.top())),
            "tr": QPoint(int(rect.right()), int(rect.top())),
            "bl": QPoint(int(rect.left()), int(rect.bottom())),
            "br": QPoint(int(rect.right()), int(rect.bottom())),
        }
        for name, corner in corners.items():
            if abs(point.x() - corner.x()) <= threshold and abs(point.y() - corner.y()) <= threshold:
                return name
        return None

    def clamp_box(self, box: Box) -> Box:
        w, h = self.image_size
        return Box(
            box.cls,
            max(0, min(w, box.x1)),
            max(0, min(h, box.y1)),
            max(0, min(w, box.x2)),
            max(0, min(h, box.y2)),
            box.conf,
        )

    def moved_box(self, original: Box, start: QPoint, current: QPoint) -> Box:
        dx = current.x() - start.x()
        dy = current.y() - start.y()
        rect = original.rect()
        w, h = self.image_size
        max_left = max(0.0, float(w) - rect.width())
        max_top = max(0.0, float(h) - rect.height())
        new_left = max(0.0, min(max_left, rect.left() + dx))
        new_top = max(0.0, min(max_top, rect.top() + dy))
        return Box(original.cls, new_left, new_top, new_left + rect.width(), new_top + rect.height(), original.conf)

    def resized_box(self, original: Box, current: QPoint, handle: str) -> Box:
        x1, x2 = sorted([original.x1, original.x2])
        y1, y2 = sorted([original.y1, original.y2])
        x = current.x()
        y = current.y()
        if "l" in handle:
            x1 = x
        if "r" in handle:
            x2 = x
        if "t" in handle:
            y1 = y
        if "b" in handle:
            y2 = y
        return self.clamp_box(Box(original.cls, x1, y1, x2, y2, original.conf))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111827"))
        if not self.pixmap:
            painter.setPen(QColor("#d1d5db"))
            painter.drawText(self.rect(), Qt.AlignCenter, "请选择图片文件夹或抽帧")
            return
        draw_rect = self.image_rect()
        painter.drawPixmap(draw_rect.toRect(), self.pixmap)

        for idx, box in enumerate(self.boxes):
            color = SELECTED_COLOR if idx == self.selected else BOX_COLORS[box.cls % len(BOX_COLORS)]
            pen = QPen(color, 4 if idx == self.selected else 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            rect = self.image_to_widget_rect(box)
            painter.drawRect(rect)
            name = self.labels[box.cls] if 0 <= box.cls < len(self.labels) else str(box.cls)
            suffix = "" if box.conf is None else f" {box.conf:.2f}"
            label = f"{name}{suffix}"
            painter.fillRect(QRectF(rect.left(), max(0, rect.top() - 22), max(70, len(label) * 9), 22), TEXT_BG)
            painter.setPen(color)
            painter.drawText(int(rect.left() + 4), int(max(16, rect.top() - 6)), label)
            if idx == self.selected:
                painter.setPen(QPen(QColor("#111827"), 1))
                painter.setBrush(SELECTED_COLOR)
                handle_size = 8
                for corner in [rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()]:
                    painter.drawRect(QRectF(corner.x() - handle_size / 2, corner.y() - handle_size / 2, handle_size, handle_size))

        if self.drawing and self.start_image and self.current_image:
            draft = Box(self.current_cls, self.start_image.x(), self.start_image.y(), self.current_image.x(), self.current_image.y())
            painter.setPen(QPen(QColor("#FFB000"), 2, Qt.DashLine))
            painter.drawRect(self.image_to_widget_rect(draft))

    def mousePressEvent(self, event) -> None:
        point = self.widget_to_image(event.position().toPoint())
        if point is None:
            return
        clicked = self.hit_test_box(point)
        if clicked >= 0:
            self.selected = clicked
            self.selection_changed.emit(clicked)
            self.drag_mode = "move"
            self.drag_start_image = point
            selected_box = self.boxes[clicked]
            self.drag_original_box = Box(selected_box.cls, selected_box.x1, selected_box.y1, selected_box.x2, selected_box.y2, selected_box.conf)
            self.resize_handle = self.hit_resize_handle(selected_box, point)
            if self.resize_handle:
                self.drag_mode = "resize"
            self.drag_changed = False
            self.update()
            return
        self.drawing = True
        self.start_image = point
        self.current_image = point
        self.selected = -1
        self.selection_changed.emit(-1)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        point = self.widget_to_image(event.position().toPoint())
        if point is None:
            return
        if self.drawing:
            self.current_image = point
            self.update()
            return
        if self.drag_mode and self.drag_start_image and self.drag_original_box and 0 <= self.selected < len(self.boxes):
            if self.drag_mode == "move":
                self.boxes[self.selected] = self.moved_box(self.drag_original_box, self.drag_start_image, point)
            elif self.drag_mode == "resize" and self.resize_handle:
                self.boxes[self.selected] = self.resized_box(self.drag_original_box, point, self.resize_handle)
            self.drag_changed = True
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self.drag_mode:
            if self.drag_changed and 0 <= self.selected < len(self.boxes):
                if self.boxes[self.selected].rect().width() < 4 or self.boxes[self.selected].rect().height() < 4:
                    if self.drag_original_box is not None:
                        self.boxes[self.selected] = self.drag_original_box
                else:
                    self.boxes_changed.emit()
            self.drag_mode = None
            self.drag_start_image = None
            self.drag_original_box = None
            self.resize_handle = None
            self.drag_changed = False
            self.update()
            return
        if not self.drawing or not self.start_image:
            return
        point = self.widget_to_image(event.position().toPoint())
        self.drawing = False
        if point is not None:
            box = Box(self.current_cls, self.start_image.x(), self.start_image.y(), point.x(), point.y())
            if box.rect().width() >= 4 and box.rect().height() >= 4:
                self.boxes.append(box)
                self.selected = len(self.boxes) - 1
                self.selection_changed.emit(self.selected)
                self.boxes_changed.emit()
        self.start_image = None
        self.current_image = None
        self.update()

    def delete_selected(self) -> None:
        if 0 <= self.selected < len(self.boxes):
            self.boxes.pop(self.selected)
            self.selected = -1
            self.selection_changed.emit(-1)
            self.boxes_changed.emit()
            self.update()

    def clear_boxes(self) -> None:
        if self.boxes:
            self.boxes = []
            self.selected = -1
            self.selection_changed.emit(-1)
            self.boxes_changed.emit()
            self.update()

    def set_selected_class(self, cls: int) -> None:
        if 0 <= self.selected < len(self.boxes):
            self.boxes[self.selected].cls = cls
            self.boxes_changed.emit()
            self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
            return
        if event.key() == Qt.Key_Escape:
            self.drawing = False
            self.drag_mode = None
            self.start_image = None
            self.current_image = None
            self.drag_start_image = None
            self.drag_original_box = None
            self.resize_handle = None
            self.update()
            return
        super().keyPressEvent(event)


@dataclass
class AiParams:
    weights: str
    labels: list[str]
    selected_cls: int
    conf: float
    imgsz: int
    device: str
    output_root: Path


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
            write_data_yaml(self.params.output_root, self.params.labels)
            image_dir = self.params.output_root / "images" / "train"
            label_dir = self.params.output_root / "labels" / "train"
            image_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            model = YOLO(self.params.weights)
            model_names = {int(k): str(v) for k, v in getattr(model, "names", {}).items()}
            total_boxes = 0
            for idx, src in enumerate(self.image_paths, 1):
                frame = load_image(src)
                stem = safe_stem(src.stem)
                dst_img = image_dir / f"{stem}.jpg"
                save_image(dst_img, frame)
                boxes = predict_boxes(model, frame, self.params, model_names)
                write_labels_file(label_dir / f"{stem}.txt", boxes, frame.shape[1], frame.shape[0])
                total_boxes += len(boxes)
                self.progress.emit(idx, len(self.image_paths), src.name)
            self.done.emit({"images": len(self.image_paths), "boxes": total_boxes, "output": str(self.params.output_root)})
        except Exception:
            self.failed.emit(traceback.format_exc())


class ImageScanWorker(QObject):
    progress = Signal(int, int, str)
    done = Signal(list, list, str)
    failed = Signal(str)

    def __init__(self, folder: Path, output_root: Path) -> None:
        super().__init__()
        self.folder = folder
        self.output_root = output_root

    def run(self) -> None:
        try:
            rows: list[tuple[str, int]] = []
            count = 0
            for root, _, files in os.walk(self.folder):
                for filename in files:
                    suffix = Path(filename).suffix.lower()
                    if suffix not in IMAGE_SUFFIXES:
                        continue
                    path = Path(root) / filename
                    label_path = label_path_for_image_path(path, self.output_root)
                    rows.append((str(path), count_yolo_labels(label_path)))
                    count += 1
                    if count % 5000 == 0:
                        self.progress.emit(count, count, f"已扫描 {count} 张图片")
            rows.sort(key=lambda item: item[0].lower())
            self.done.emit([path for path, _ in rows], [box_count for _, box_count in rows], str(self.folder))
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
                resolved = image_path.resolve()
                try:
                    resolved.relative_to(image_dir)
                except ValueError:
                    continue
                label_path = label_dir / f"{safe_stem(image_path.stem)}.txt"
                if count_yolo_labels(label_path) == 0:
                    image_path.unlink(missing_ok=True)
                    label_path.unlink(missing_ok=True)
                    deleted += 1
                if idx % 5000 == 0:
                    self.progress.emit(idx, total, f"已检查 {idx} 张，删除 {deleted} 张")
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
    ) -> None:
        super().__init__()
        self.video_paths = video_paths
        self.frame_step = frame_step
        self.max_frames = max_frames
        self.output_root = output_root
        self.labels = labels
        self.params = params

    def run(self) -> None:
        try:
            output_root = self.output_root
            labels = self.labels
            write_data_yaml(output_root, labels)
            image_dir = output_root / "images" / "train"
            label_dir = output_root / "labels" / "train"
            image_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            model = YOLO(self.params.weights) if self.params else None
            model_names = {int(k): str(v) for k, v in getattr(model, "names", {}).items()} if model else {}

            total_frames = 0
            total_boxes = 0
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
                        dst_img = image_dir / f"{stem}.jpg"
                        save_image(dst_img, frame)
                        if model is not None and self.params is not None:
                            boxes = predict_boxes(model, frame, self.params, model_names)
                        else:
                            boxes = []
                        write_labels_file(label_dir / f"{stem}.txt", boxes, frame.shape[1], frame.shape[0])
                        total_boxes += len(boxes)
                        total_frames += 1
                        saved += 1
                        if self.max_frames > 0 and saved >= self.max_frames:
                            break
                    frame_idx += 1
                cap.release()
                self.progress.emit(video_idx, total_jobs, video.name)
            self.done.emit({"frames": total_frames, "boxes": total_boxes, "output": str(output_root)})
        except Exception:
            self.failed.emit(traceback.format_exc())


def predict_boxes(model: YOLO, frame: np.ndarray, params: AiParams, model_names: dict[int, str]) -> list[Box]:
    result = model.predict(frame, conf=params.conf, imgsz=params.imgsz, device=params.device, verbose=False)[0]
    boxes: list[Box] = []
    if result.boxes is None:
        return boxes
    label_map = {name: idx for idx, name in enumerate(params.labels)}
    for xyxy, conf, cls in zip(result.boxes.xyxy.cpu().numpy(), result.boxes.conf.cpu().numpy(), result.boxes.cls.cpu().numpy()):
        model_cls = int(cls)
        model_name = model_names.get(model_cls, "")
        target_cls = label_map.get(model_name, params.selected_cls)
        x1, y1, x2, y2 = [float(v) for v in xyxy]
        boxes.append(Box(target_cls, x1, y1, x2, y2, float(conf)))
    return boxes


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CVDS AI 辅助 YOLO 标注工具")
        self.resize(1450, 860)
        self.image_paths: list[Path] = []
        self.current_index = -1
        self.current_frame: np.ndarray | None = None
        self.worker_thread: QThread | None = None
        self.worker: QObject | None = None
        self.after_worker_callback = None

        self.canvas = ImageCanvas()
        self.image_model = ImageListModel()
        self.image_list = QListView()
        self.image_list.setModel(self.image_model)
        self.image_list.setUniformItemSizes(True)
        self.image_list.setAlternatingRowColors(True)
        self.image_list.setSelectionMode(QListView.SingleSelection)
        self.image_list.selectionModel().currentChanged.connect(self.on_image_current_changed)
        self.canvas.boxes_changed.connect(self.refresh_box_table)
        self.canvas.selection_changed.connect(self.on_selection_changed)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        left = self.build_left_panel()
        right = self.build_right_panel()
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([390, 1050])
        layout.addWidget(splitter)
        self.statusBar().showMessage(self.device_text())
        self.reload_labels()
        self.setup_shortcuts()

    def build_left_panel(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

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

        label_box = QGroupBox("标签")
        label_layout = QVBoxLayout(label_box)
        self.labels_edit = QPlainTextEdit("parcel")
        self.labels_edit.setMinimumHeight(90)
        self.labels_edit.textChanged.connect(self.reload_labels)
        self.class_combo = QComboBox()
        self.class_combo.currentIndexChanged.connect(self.change_current_class)
        label_layout.addWidget(self.labels_edit)
        label_layout.addWidget(self.class_combo)

        ai_box = QGroupBox("AI 标注参数")
        ai_form = QFormLayout(ai_box)
        self.conf_edit = QLineEdit("0.25")
        self.imgsz_spin = QSpinBox()
        self.imgsz_spin.setRange(160, 1536)
        self.imgsz_spin.setValue(960)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["0" if torch.cuda.is_available() else "cpu", "cpu"])
        ai_form.addRow("置信度", self.conf_edit)
        ai_form.addRow("输入尺寸", self.imgsz_spin)
        ai_form.addRow("设备", self.device_combo)

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

        btn_box = QGroupBox("操作")
        btn_layout = QGridLayout(btn_box)
        self.scan_btn = QPushButton("加载图片")
        self.scan_btn.clicked.connect(self.scan_images)
        self.ai_btn = QPushButton("AI批量标注图片")
        self.ai_btn.clicked.connect(self.ai_label_images)
        self.extract_btn = QPushButton("视频批量抽帧")
        self.extract_btn.clicked.connect(lambda: self.extract_videos(False))
        self.extract_ai_btn = QPushButton("抽帧并AI标注")
        self.extract_ai_btn.clicked.connect(lambda: self.extract_videos(True))
        self.save_btn = QPushButton("保存当前")
        self.save_btn.clicked.connect(self.save_current)
        self.delete_btn = QPushButton("删除选中框")
        self.delete_btn.clicked.connect(self.delete_selected_box)
        btn_layout.addWidget(self.scan_btn, 0, 0)
        btn_layout.addWidget(self.ai_btn, 0, 1)
        btn_layout.addWidget(self.extract_btn, 1, 0)
        btn_layout.addWidget(self.extract_ai_btn, 1, 1)
        btn_layout.addWidget(self.save_btn, 2, 0)
        btn_layout.addWidget(self.delete_btn, 2, 1)

        manual_box = QGroupBox("手工辅助")
        manual_layout = QGridLayout(manual_box)
        self.save_next_btn = QPushButton("保存并下一张")
        self.save_next_btn.clicked.connect(self.save_and_next)
        self.clear_boxes_btn = QPushButton("清空当前框")
        self.clear_boxes_btn.clicked.connect(self.clear_current_boxes)
        self.copy_prev_btn = QPushButton("复制上一张框")
        self.copy_prev_btn.clicked.connect(self.copy_previous_boxes)
        self.next_empty_btn = QPushButton("下一个空标注")
        self.next_empty_btn.clicked.connect(self.goto_next_empty_label)
        self.delete_frame_btn = QPushButton("删除当前空帧")
        self.delete_frame_btn.clicked.connect(self.delete_current_empty_frame)
        self.delete_empty_btn = QPushButton("删除空标签帧")
        self.delete_empty_btn.clicked.connect(self.delete_empty_label_frames)
        manual_layout.addWidget(self.save_next_btn, 0, 0)
        manual_layout.addWidget(self.clear_boxes_btn, 0, 1)
        manual_layout.addWidget(self.copy_prev_btn, 1, 0)
        manual_layout.addWidget(self.next_empty_btn, 1, 1)
        manual_layout.addWidget(self.delete_frame_btn, 2, 0)
        manual_layout.addWidget(self.delete_empty_btn, 2, 1)

        self.progress = QProgressBar()
        self.progress.hide()
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(160)

        layout.addWidget(io_box)
        layout.addWidget(label_box)
        layout.addWidget(ai_box)
        layout.addWidget(video_box)
        layout.addWidget(btn_box)
        layout.addWidget(manual_box)
        layout.addWidget(self.progress)
        layout.addWidget(QLabel("图片列表"))
        layout.addWidget(self.image_list, 1)
        layout.addWidget(self.log)
        return page

    def build_right_panel(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        nav = QHBoxLayout()
        prev_btn = QPushButton("上一张")
        next_btn = QPushButton("下一张")
        prev_btn.clicked.connect(lambda: self.step_image(-1))
        next_btn.clicked.connect(lambda: self.step_image(1))
        self.info_label = QLabel("未加载")
        nav.addWidget(prev_btn)
        nav.addWidget(next_btn)
        nav.addWidget(self.info_label, 1)
        self.box_table = QTableWidget(0, 5)
        self.box_table.setHorizontalHeaderLabels(["类别", "x1", "y1", "x2", "y2"])
        self.box_table.cellClicked.connect(self.select_box_from_table)
        layout.addLayout(nav)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(QLabel("当前图片标注框"))
        layout.addWidget(self.box_table)
        return page

    def device_text(self) -> str:
        if torch.cuda.is_available():
            return f"CUDA 可用：{torch.cuda.get_device_name(0)}"
        return "CUDA 不可用：当前环境将使用 CPU"

    def setup_shortcuts(self) -> None:
        self.shortcuts: list[QShortcut] = []
        bindings = [
            ("Ctrl+S", self.save_current),
            ("Ctrl+Left", lambda: self.step_image(-1)),
            ("Ctrl+Right", lambda: self.step_image(1)),
            ("Ctrl+Shift+S", self.save_and_next),
            ("Ctrl+E", self.goto_next_empty_label),
        ]
        for sequence, callback in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    def labels(self) -> list[str]:
        labels = [line.strip() for line in self.labels_edit.toPlainText().splitlines() if line.strip()]
        return labels or ["parcel"]

    def reload_labels(self) -> None:
        labels = self.labels()
        current = self.class_combo.currentIndex()
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        self.class_combo.addItems(labels)
        self.class_combo.setCurrentIndex(max(0, min(current, len(labels) - 1)))
        self.class_combo.blockSignals(False)
        self.canvas.set_labels(labels)
        self.canvas.set_current_cls(self.class_combo.currentIndex())
        write_data_yaml(Path(self.output_edit.text()), labels)

    def set_labels_from_yolo_folder(self, output_root: Path) -> None:
        labels = read_data_yaml_labels(output_root)
        if labels:
            self.labels_edit.blockSignals(True)
            self.labels_edit.setPlainText("\n".join(labels))
            self.labels_edit.blockSignals(False)
            self.reload_labels()

    def change_current_class(self, index: int) -> None:
        self.canvas.set_current_cls(index)
        self.canvas.set_selected_class(index)
        self.refresh_box_table()

    def pick_weights(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择模型权重", str(ROOT / "weights"), "PyTorch (*.pt)")
        if path:
            self.weights_edit.setText(path)

    def pick_image_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择图片文件夹", str(ROOT))
        if path:
            self.image_folder_edit.setText(path)

    def pick_video_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择视频文件夹", str(ROOT))
        if path:
            self.video_folder_edit.setText(path)

    def pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择YOLO输出目录", str(ROOT / "datasets"))
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
        return Path(self.output_edit.text()).resolve()

    def label_path_for_image(self, image_path: Path) -> Path:
        return label_path_for_image_path(image_path, self.output_root())

    def output_image_path(self, image_path: Path) -> Path:
        return self.output_root() / "images" / "train" / f"{safe_stem(image_path.stem)}.jpg"

    def is_output_image_path(self, image_path: Path) -> bool:
        image_dir = (self.output_root() / "images" / "train").resolve()
        resolved = image_path.resolve()
        try:
            resolved.relative_to(image_dir)
            return True
        except ValueError:
            return False

    def is_label_empty(self, image_path: Path) -> bool:
        label_path = self.label_path_for_image(image_path)
        if not label_path.exists():
            return True
        return label_path.read_text(encoding="utf-8", errors="ignore").strip() == ""

    def update_image_list_item(self, row: int, box_count: int) -> None:
        self.image_model.update_box_count(row, box_count)

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
        self.append_log(f"开始后台扫描图片：{folder}")
        self.worker_thread = QThread()
        self.worker = ImageScanWorker(folder, self.output_root())
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
        self.image_paths = [Path(path) for path in paths]
        self.current_index = -1
        self.current_frame = None
        self.canvas.set_image(None)
        self.canvas.set_boxes([])
        self.image_model.set_paths(self.image_paths, box_counts)
        if self.image_paths:
            self.image_list.setCurrentIndex(self.image_model.index(0, 0))
        else:
            self.info_label.setText("未加载")
            self.refresh_box_table()
        self.append_log(f"加载图片 {len(self.image_paths)} 张：{folder}")

    def on_image_current_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        self.goto_image(current.row())

    def goto_image(self, row: int) -> None:
        if row < 0 or row >= len(self.image_paths):
            return
        self.save_current(silent=True)
        self.current_index = row
        path = self.image_paths[row]
        frame = load_image(path)
        self.current_frame = frame
        h, w = frame.shape[:2]
        boxes = read_labels_file(self.label_path_for_image(path), w, h)
        self.canvas.set_image(frame)
        self.canvas.set_labels(self.labels())
        self.canvas.set_boxes(boxes)
        self.info_label.setText(f"{row + 1}/{len(self.image_paths)}  {path.name}  {w}x{h}")
        self.update_image_list_item(row, len(boxes))
        self.refresh_box_table()

    def step_image(self, step: int) -> None:
        if not self.image_paths:
            return
        target = max(0, min(len(self.image_paths) - 1, self.current_index + step))
        self.image_list.setCurrentIndex(self.image_model.index(target, 0))

    def save_current(self, silent: bool = False) -> None:
        if self.current_index < 0 or self.current_frame is None:
            return
        self.reload_labels()
        path = self.image_paths[self.current_index]
        dst_img = self.output_image_path(path)
        if path.resolve() != dst_img.resolve():
            save_image(dst_img, self.current_frame)
            label_path = self.output_root() / "labels" / "train" / f"{dst_img.stem}.txt"
        else:
            label_path = self.label_path_for_image(path)
        h, w = self.current_frame.shape[:2]
        write_labels_file(label_path, self.canvas.boxes, w, h)
        self.update_image_list_item(self.current_index, len(self.canvas.boxes))
        if not silent:
            self.append_log(f"已保存：{label_path}")

    def refresh_box_table(self) -> None:
        self.box_table.setRowCount(len(self.canvas.boxes))
        labels = self.labels()
        for row, box in enumerate(self.canvas.boxes):
            name = labels[box.cls] if 0 <= box.cls < len(labels) else str(box.cls)
            values = [name, box.x1, box.y1, box.x2, box.y2]
            for col, value in enumerate(values):
                text = value if isinstance(value, str) else f"{value:.1f}"
                self.box_table.setItem(row, col, QTableWidgetItem(text))
        self.update_image_list_item(self.current_index, len(self.canvas.boxes))

    def on_selection_changed(self, idx: int) -> None:
        if 0 <= idx < self.box_table.rowCount():
            self.box_table.selectRow(idx)

    def select_box_from_table(self, row: int, col: int) -> None:
        self.canvas.selected = row
        self.canvas.update()

    def delete_selected_box(self) -> None:
        self.canvas.delete_selected()
        self.refresh_box_table()

    def save_and_next(self) -> None:
        if self.current_index < 0:
            return
        self.save_current()
        self.step_image(1)

    def clear_current_boxes(self) -> None:
        if self.current_index < 0:
            return
        self.canvas.set_boxes([])
        self.refresh_box_table()
        self.save_current(silent=True)
        self.append_log("已清空当前图片标注框")

    def copy_previous_boxes(self) -> None:
        if self.current_index <= 0 or self.current_frame is None:
            QMessageBox.information(self, "没有上一张", "当前图片前面没有可复制的图片")
            return
        prev_path = self.image_paths[self.current_index - 1]
        prev_frame = load_image(prev_path)
        prev_h, prev_w = prev_frame.shape[:2]
        cur_h, cur_w = self.current_frame.shape[:2]
        prev_boxes = read_labels_file(self.label_path_for_image(prev_path), prev_w, prev_h)
        if not prev_boxes:
            QMessageBox.information(self, "没有标注框", "上一张图片没有可复制的标注框")
            return
        scale_x = cur_w / prev_w
        scale_y = cur_h / prev_h
        copied = [
            Box(box.cls, box.x1 * scale_x, box.y1 * scale_y, box.x2 * scale_x, box.y2 * scale_y)
            for box in prev_boxes
        ]
        self.canvas.set_boxes(copied)
        self.refresh_box_table()
        self.append_log(f"已复制上一张标注框：{len(copied)} 个")

    def goto_next_empty_label(self) -> None:
        if not self.image_paths:
            return
        self.save_current(silent=True)
        start = max(0, self.current_index + 1)
        order = list(range(start, len(self.image_paths))) + list(range(0, start))
        for row in order:
            count = self.image_model.box_count(row)
            if count == 0 or (count is None and self.is_label_empty(self.image_paths[row])):
                self.image_list.setCurrentIndex(self.image_model.index(row, 0))
                return
        QMessageBox.information(self, "没有空标注", "当前列表里没有空标注图片")

    def delete_current_empty_frame(self) -> None:
        self.delete_current_sample(require_empty=True)

    def delete_current_sample(self, require_empty: bool) -> None:
        if self.current_index < 0 or self.current_index >= len(self.image_paths):
            return
        if require_empty and self.canvas.boxes:
            QMessageBox.warning(self, "当前不是空帧", "当前图片还有标注框，请先确认并清空标注框")
            return
        image_path = self.image_paths[self.current_index]
        if not self.is_output_image_path(image_path):
            QMessageBox.warning(self, "不能删除原始图片", "当前图片不在输出目录中，只能删除抽帧或已保存到输出目录的图片")
            return
        label_path = self.label_path_for_image(image_path)
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除当前空帧和对应标签吗？\n{image_path.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        row = self.current_index
        image_path.unlink(missing_ok=True)
        label_path.unlink(missing_ok=True)
        self.image_paths.pop(row)
        self.image_model.remove_row(row)
        self.current_index = -1
        self.current_frame = None
        self.canvas.set_image(None)
        self.canvas.set_boxes([])
        self.append_log(f"已删除空帧：{image_path.name}")
        if self.image_paths:
            self.image_list.setCurrentIndex(self.image_model.index(min(row, len(self.image_paths) - 1), 0))
        else:
            self.info_label.setText("未加载")
            self.refresh_box_table()

    def delete_empty_label_frames(self) -> None:
        if not self.image_paths:
            return
        self.save_current(silent=True)
        reply = QMessageBox.question(
            self,
            "确认批量删除",
            "将后台检查当前列表，删除输出目录中所有空标签帧和对应标签。确认这些图片里都没有包裹后再删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.start_worker(DeleteEmptyLabelsWorker(list(self.image_paths), self.output_root()), self.scan_output_images)

    def ai_params(self) -> AiParams:
        labels = self.labels()
        selected = max(0, min(self.class_combo.currentIndex(), len(labels) - 1))
        return AiParams(
            weights=self.weights_edit.text(),
            labels=labels,
            selected_cls=selected,
            conf=float(self.conf_edit.text()),
            imgsz=self.imgsz_spin.value(),
            device=self.device_combo.currentText(),
            output_root=self.output_root(),
        )

    def ai_label_images(self) -> None:
        image_paths = list(self.image_paths)
        if not image_paths:
            QMessageBox.warning(self, "没有图片", "请先点击“加载图片”，后台扫描完成后再批量标注")
            return
        self.start_worker(ImageAutoLabelWorker(image_paths, self.ai_params()), self.scan_output_images)

    def extract_videos(self, do_ai: bool) -> None:
        folder = Path(self.video_folder_edit.text())
        videos = sorted([p for p in folder.rglob("*") if p.suffix.lower() in VIDEO_SUFFIXES])
        if not videos:
            QMessageBox.warning(self, "没有视频", "视频文件夹内没有可抽帧视频")
            return
        params = self.ai_params() if do_ai else None
        worker = VideoExtractWorker(
            videos,
            self.frame_step_spin.value(),
            self.max_frames_spin.value(),
            self.output_root(),
            self.labels(),
            params,
        )
        self.start_worker(worker, self.scan_output_images)

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
        self.progress.setValue(int(current / max(1, total) * 100))
        self.append_log(f"{current}/{total} {text}")

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
        callback = self.after_worker_callback
        self.after_worker_callback = None
        if callback is not None:
            callback()

    def set_controls_enabled(self, enabled: bool) -> None:
        for widget in [
            self.scan_btn,
            self.ai_btn,
            self.extract_btn,
            self.extract_ai_btn,
            self.save_btn,
            self.delete_btn,
            self.save_next_btn,
            self.clear_boxes_btn,
            self.copy_prev_btn,
            self.next_empty_btn,
            self.delete_frame_btn,
            self.delete_empty_btn,
            self.load_yolo_btn,
        ]:
            widget.setEnabled(enabled)

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text)


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
