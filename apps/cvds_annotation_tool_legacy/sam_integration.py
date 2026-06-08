"""
CVDS 标注工具 - SAM 半自动分割集成模块

设计目标:
- 与主文件解耦,主文件只需 import 本模块并调用 install_sam_into_main_window
- 复用主文件的 Annotation / DefectAnnotation / 延迟导入函数
- 支持 MobileSAM / SAM2,默认 MobileSAM(速度优先)
- 交互方式:
    左键拉框    -> SAM 出预览 mask
    Shift+左键  -> 加正点(目标内)
    右键        -> 加负点(背景)
    回车        -> 接受预览 mask 为正式标注
    Esc         -> 撤销/取消
- 推理在后台线程,避免主线程卡顿
- 输出 polygon 经 Douglas-Peucker 简化,顶点数控制在 30-80
- 同一张图反复 prompt 时复用 image embedding(由 ultralytics 内部缓存)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QPolygonF, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    import numpy as np


# ========================================================================
# 常量
# ========================================================================

SAM_MODE_NAME = "SAM 半自动 (segment)"
SAM_PREVIEW_COLOR = QColor("#22c55e")
SAM_POS_POINT_COLOR = QColor("#22c55e")
SAM_NEG_POINT_COLOR = QColor("#ef4444")
SAM_BOX_COLOR = QColor("#22c55e")

DEFAULT_SAM_VARIANTS = [
    ("MobileSAM (推荐,40MB,~80ms)", "mobile_sam.pt"),
    ("SAM2.1 Tiny (78MB,精度更高)", "sam2.1_t.pt"),
    ("SAM2.1 Small (185MB)", "sam2.1_s.pt"),
    ("SAM ViT-B (375MB,较慢)", "sam_b.pt"),
]


# ========================================================================
# 延迟导入
# ========================================================================

_SAM_CLS = None


def get_sam_cls():
    global _SAM_CLS
    if _SAM_CLS is None:
        from ultralytics import SAM
        _SAM_CLS = SAM
    return _SAM_CLS


# ========================================================================
# 工具函数
# ========================================================================


def simplify_polygon(
    points: list[tuple[float, float]],
    min_vertices: int = 4,
    relative_epsilon: float = 0.003,
) -> list[tuple[float, float]]:
    """用 Douglas-Peucker 算法把 SAM 返回的稠密轮廓简化到合理顶点数。

    SAM 通常返回数百顶点,直接落到 YOLO seg 标签会让文件巨大、画布拖动卡顿。
    这里按周长比例自适应 epsilon,典型结果在 20-80 顶点。
    """
    if len(points) < min_vertices:
        return points
    try:
        from cvds_annotation_tool_v2 import get_cv2, get_np  # 复用主文件的延迟导入
    except ImportError:
        # 如果模块名不同,fallback 到直接 import
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        cv2_module = cv2
        np_module = np
    else:
        cv2_module = get_cv2()
        np_module = get_np()
    contour = np_module.array(points, dtype=np_module.float32).reshape(-1, 1, 2)
    perimeter = cv2_module.arcLength(contour, True)
    if perimeter <= 0:
        return points
    eps = max(1.0, perimeter * relative_epsilon)
    approx = cv2_module.approxPolyDP(contour, eps, True)
    simplified = [(float(p[0][0]), float(p[0][1])) for p in approx]
    return simplified if len(simplified) >= 3 else points


def points_inside_rect(points: list[tuple[float, float]], rect: QRectF, margin: float = 1.0) -> bool:
    """判断 polygon 是否完整落在某个矩形内(用于缺陷模式校验)。"""
    if not points:
        return False
    return all(
        rect.left() - margin <= x <= rect.right() + margin
        and rect.top() - margin <= y <= rect.bottom() + margin
        for x, y in points
    )


# ========================================================================
# 推理服务
# ========================================================================


@dataclass
class SamRequest:
    kind: str  # 'box' or 'points'
    bbox: tuple[float, float, float, float] | None = None
    points: list[tuple[float, float]] | None = None
    labels: list[int] | None = None
    image_id: str = ""


class SamService(QObject):
    """SAM 模型管理 + 单帧 prompt 推理。

    线程模型:本对象在工作线程中持有 model,主线程通过信号与之通信。
    """

    mask_ready = Signal(object, str)  # polygon, image_id
    failed = Signal(str)
    loaded = Signal(str)  # weights name

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

    def set_image(self, frame: "np.ndarray", image_id: str) -> None:
        self._current_frame = frame
        self._current_image_id = image_id

    def has_image(self) -> bool:
        return self._current_frame is not None

    def handle_request(self, request: SamRequest) -> None:
        """统一入口,在工作线程中调用。"""
        try:
            self.ensure_model()
            if self._current_frame is None:
                self.failed.emit("当前没有图片可供 SAM 推理")
                return
            if request.image_id and request.image_id != self._current_image_id:
                # 用户已经翻页,丢弃过期请求
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
        except Exception as exc:  # noqa: BLE001
            import traceback
            self.failed.emit(traceback.format_exc())

    def release(self) -> None:
        """主动释放显存。"""
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
            xy = masks.xy  # list[np.ndarray (N,2)]
        except Exception:  # noqa: BLE001
            return None
        if not xy or len(xy[0]) < 3:
            return None
        raw = [(float(x), float(y)) for x, y in xy[0]]
        return simplify_polygon(raw)


# ========================================================================
# 后台调度器
# ========================================================================


class SamController(QObject):
    """运行在主线程,负责把请求派发到 SamService 工作线程,并节流。"""

    request_to_service = Signal(SamRequest)
    mask_ready = Signal(object, str)  # polygon, image_id
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
        # 这里直接跨线程调用是安全的,因为 numpy 数组只是引用赋值,
        # 且我们保证主线程不会再修改它(每次切图都是新的 frame)。
        self.service.set_image(frame, image_id)

    def submit(self, request: SamRequest) -> None:
        if self._busy:
            self._pending = request  # 只保留最新请求,丢弃中间帧
            return
        self._set_busy(True)
        self.request_to_service.emit(request)

    def _on_mask(self, polygon, image_id: str) -> None:
        self._set_busy(False)
        self.mask_ready.emit(polygon, image_id)
        if self._pending is not None:
            req = self._pending
            self._pending = None
            self.submit(req)

    def _on_failed(self, msg: str) -> None:
        self._set_busy(False)
        self.failed.emit(msg)
        if self._pending is not None:
            req = self._pending
            self._pending = None
            self.submit(req)

    def shutdown(self) -> None:
        try:
            self.service.release()
        except Exception:  # noqa: BLE001
            pass
        self.thread.quit()
        self.thread.wait(3000)


# ========================================================================
# 画布交互状态(挂在 ImageCanvas 上)
# ========================================================================


class SamCanvasState:
    """把 SAM 相关的画布状态从 ImageCanvas 拆出来,避免污染原类。"""

    def __init__(self) -> None:
        self.active = False
        self.drawing_box = False
        self.box_start: QPointF | None = None
        self.box_current: QPointF | None = None
        self.points: list[tuple[float, float]] = []
        self.labels: list[int] = []  # 1=正点,0=负点
        self.preview_polygon: list[tuple[float, float]] | None = None
        self.target_defect: bool = False  # 是否把结果落到 defects 而不是 annotations
        self.target_parent_index: int = -1  # 缺陷模式下的父框 index

    def reset(self) -> None:
        self.drawing_box = False
        self.box_start = None
        self.box_current = None
        self.points = []
        self.labels = []
        self.preview_polygon = None
        self.target_defect = False
        self.target_parent_index = -1

    def has_prompt(self) -> bool:
        return bool(self.preview_polygon or self.points or self.drawing_box)


# ========================================================================
# 与 MainWindow 的整合入口
# ========================================================================


class SamIntegration(QObject):
    """主整合类。挂载到 MainWindow 上,负责 UI、信号、状态机协调。"""

    log_message = Signal(str)

    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self.mw = main_window
        self.canvas = main_window.canvas
        self.controller: SamController | None = None
        self.sam_state = SamCanvasState()
        self._attach_state_to_canvas()
        self._patch_canvas_methods()
        self._build_ui()
        self._install_shortcuts()

    # ----------------------------------------------------------------
    # 状态机
    # ----------------------------------------------------------------

    def _attach_state_to_canvas(self) -> None:
        # 把 sam_state 直接挂到 canvas 上,paintEvent 时可以访问
        self.canvas.sam_state = self.sam_state
        self.canvas.sam_integration = self

    def is_active(self) -> bool:
        return self.sam_state.active

    def activate(self, for_defect: bool = False) -> None:
        self.sam_state.reset()
        self.sam_state.active = True
        self.sam_state.target_defect = for_defect
        if for_defect:
            parent = self.canvas.selected_parent_for_defect()
            self.sam_state.target_parent_index = parent
            if parent < 0:
                self.log_message.emit("SAM 缺陷模式:请先选择一个目标实例")
        if self.controller is None:
            if not self._init_controller():
                self.sam_state.active = False
                return
        # 同步当前帧到 SAM
        if self.mw.current_frame is not None and self.mw.current_index >= 0:
            self.controller.set_image(
                self.mw.current_frame,
                str(self.mw.image_paths[self.mw.current_index]),
            )
        self.canvas.setCursor(Qt.CrossCursor)
        self.canvas.update()

    def deactivate(self) -> None:
        self.sam_state.reset()
        self.sam_state.active = False
        self.canvas.update()

    def on_image_changed(self) -> None:
        """主窗口在切图时调用。"""
        self.sam_state.reset()
        if self.controller is not None and self.mw.current_frame is not None and self.mw.current_index >= 0:
            self.controller.set_image(
                self.mw.current_frame,
                str(self.mw.image_paths[self.mw.current_index]),
            )
        self.canvas.update()

    # ----------------------------------------------------------------
    # Controller 初始化
    # ----------------------------------------------------------------

    def _init_controller(self) -> bool:
        weights = self.weights_edit.text().strip()
        if not weights:
            QMessageBox.warning(self.mw, "未配置 SAM 权重", "请先在 SAM 区域选择权重文件")
            return False
        path = Path(weights)
        if not path.exists() and not path.name.lower().startswith(("mobile_sam", "sam2", "sam_b", "sam_l", "sam_h")):
            QMessageBox.warning(
                self.mw, "SAM 权重不存在",
                f"找不到 {weights}\n\nultralytics 支持的名称(会自动下载):\n"
                "  mobile_sam.pt\n  sam2.1_t.pt / sam2.1_s.pt\n  sam_b.pt / sam_l.pt",
            )
            return False
        device = self.mw.device_combo.currentText()
        self.log_message.emit(f"初始化 SAM:{weights} @ {device}")
        try:
            self.controller = SamController(weights, device, parent=self)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.mw, "SAM 初始化失败", str(exc))
            return False
        self.controller.mask_ready.connect(self._on_mask_ready)
        self.controller.failed.connect(self._on_failed)
        self.controller.busy_changed.connect(self._on_busy_changed)
        return True

    def shutdown(self) -> None:
        if self.controller is not None:
            self.controller.shutdown()
            self.controller = None

    # ----------------------------------------------------------------
    # UI
    # ----------------------------------------------------------------

    def _build_ui(self) -> QGroupBox:
        """在左侧面板插入一个 SAM 配置 group。

        调用方需要在主窗口构建完左面板后调用 attach_ui_to_left_panel。
        """
        box = QGroupBox("SAM 半自动分割")
        grid = QGridLayout(box)

        self.weights_edit = QLineEdit("mobile_sam.pt")
        pick_btn = QPushButton("选择")
        pick_btn.clicked.connect(self._pick_weights)
        grid.addWidget(QLabel("SAM 权重"), 0, 0)
        grid.addWidget(self.weights_edit, 0, 1)
        grid.addWidget(pick_btn, 0, 2)

        for name, fname in DEFAULT_SAM_VARIANTS:
            btn = QPushButton(name)
            btn.clicked.connect(lambda _=False, f=fname: self.weights_edit.setText(f))
            grid.addWidget(btn, 1 + DEFAULT_SAM_VARIANTS.index((name, fname)) // 2,
                           DEFAULT_SAM_VARIANTS.index((name, fname)) % 2 * 2,
                           1, 2)

        load_btn = QPushButton("加载 / 重载 SAM")
        load_btn.clicked.connect(self._reload_sam)
        grid.addWidget(load_btn, 4, 0, 1, 3)

        self.status_label = QLabel("未加载")
        self.status_label.setStyleSheet("color:#9ca3af;")
        grid.addWidget(self.status_label, 5, 0, 1, 3)

        hint = QLabel(
            "用法:Alt+S 切到 SAM 模式 → 左键拉框出 mask → "
            "Shift+左键 加正点 / 右键 加负点 修正 → 回车 接受 / Esc 取消"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#9ca3af; font-size:11px;")
        grid.addWidget(hint, 6, 0, 1, 3)

        self.ui_box = box
        return box

    def attach_ui_to_left_panel(self, insert_before_widget=None) -> None:
        """把 SAM 设置 box 插入到左侧面板。"""
        left_widget = self.mw.left_shell.widget()
        layout = left_widget.layout()
        if insert_before_widget is not None:
            idx = layout.indexOf(insert_before_widget)
            if idx >= 0:
                layout.insertWidget(idx, self.ui_box)
                return
        # fallback:插到末尾前
        layout.insertWidget(layout.count() - 3, self.ui_box)

    def _pick_weights(self) -> None:
        start = str(Path(self.weights_edit.text()).parent) if self.weights_edit.text() else ""
        path, _ = QFileDialog.getOpenFileName(self.mw, "选择 SAM 权重", start, "PyTorch (*.pt)")
        if path:
            self.weights_edit.setText(path)

    def _reload_sam(self) -> None:
        if self.controller is not None:
            self.shutdown()
        self.status_label.setText("加载中…")
        if self._init_controller():
            self.status_label.setText(f"已加载:{Path(self.weights_edit.text()).name}")
        else:
            self.status_label.setText("加载失败")

    # ----------------------------------------------------------------
    # 快捷键
    # ----------------------------------------------------------------

    def _install_shortcuts(self) -> None:
        self.sc_toggle = QShortcut(QKeySequence("Alt+S"), self.mw)
        self.sc_toggle.activated.connect(self._toggle_sam_mode)

        self.sc_accept = QShortcut(QKeySequence("Return"), self.mw)
        self.sc_accept.activated.connect(self._guarded(self._accept_preview))

        self.sc_accept2 = QShortcut(QKeySequence("Enter"), self.mw)
        self.sc_accept2.activated.connect(self._guarded(self._accept_preview))

    def _guarded(self, fn: Callable) -> Callable:
        """避免文本输入框被快捷键吃掉。"""
        def runner():
            from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit
            focus = QApplication.focusWidget()
            if isinstance(focus, (QLineEdit, QPlainTextEdit)):
                return
            fn()
        return runner

    def _toggle_sam_mode(self) -> None:
        # 找到 SAM 在 mode_combo 中的索引
        for i in range(self.mw.mode_combo.count()):
            if self.mw.mode_combo.itemText(i) == SAM_MODE_NAME:
                self.mw.mode_combo.setCurrentIndex(i)
                return

    # ----------------------------------------------------------------
    # 鼠标事件钩子
    # ----------------------------------------------------------------

    def handle_mouse_press(self, event, image_point: QPointF) -> bool:
        """返回 True 表示事件已处理,canvas 不要再走原有逻辑。"""
        if not self.is_active() or image_point is None:
            return False

        modifiers = event.modifiers()
        button = event.button()

        if button == Qt.LeftButton and (modifiers & Qt.ShiftModifier):
            # 加正点
            self._add_point(image_point, label=1)
            return True
        if button == Qt.RightButton and self.sam_state.preview_polygon:
            # 加负点(必须已有预览)
            self._add_point(image_point, label=0)
            return True
        if button == Qt.RightButton:
            # 没预览时右键 = 取消
            self.deactivate()
            self.activate(for_defect=self.sam_state.target_defect)
            return True
        if button == Qt.LeftButton and not (modifiers & Qt.ControlModifier):
            # 缺陷模式下,框必须在选中目标内
            if self.sam_state.target_defect:
                parent_idx = self.sam_state.target_parent_index
                if parent_idx < 0 or parent_idx >= len(self.canvas.annotations):
                    self.log_message.emit("SAM 缺陷模式:请先选中目标实例")
                    return True
                if not self.canvas.annotations[parent_idx].contains(image_point.x(), image_point.y()):
                    return True
            self.sam_state.drawing_box = True
            self.sam_state.box_start = image_point
            self.sam_state.box_current = image_point
            self.canvas.update()
            return True
        return False

    def handle_mouse_move(self, event, image_point: QPointF) -> bool:
        if not self.is_active() or image_point is None:
            return False
        if self.sam_state.drawing_box:
            self.sam_state.box_current = image_point
            self.canvas.update()
            return True
        return False

    def handle_mouse_release(self, event, image_point: QPointF) -> bool:
        if not self.is_active() or image_point is None:
            return False
        if self.sam_state.drawing_box and event.button() == Qt.LeftButton:
            self.sam_state.drawing_box = False
            x1 = self.sam_state.box_start.x() if self.sam_state.box_start else 0
            y1 = self.sam_state.box_start.y() if self.sam_state.box_start else 0
            x2 = image_point.x()
            y2 = image_point.y()
            if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
                # 过小,当成单点
                self._add_point(QPointF((x1 + x2) / 2, (y1 + y2) / 2), label=1)
            else:
                left, right = sorted([x1, x2])
                top, bottom = sorted([y1, y2])
                self._submit_box(left, top, right, bottom)
            self.canvas.update()
            return True
        return False

    def handle_rollback(self) -> bool:
        """Esc 撤回,返回 True 表示已消化。"""
        if not self.is_active():
            return False
        if self.sam_state.preview_polygon or self.sam_state.points:
            self.sam_state.preview_polygon = None
            self.sam_state.points = []
            self.sam_state.labels = []
            self.canvas.update()
            return True
        if self.sam_state.drawing_box:
            self.sam_state.drawing_box = False
            self.sam_state.box_start = None
            self.sam_state.box_current = None
            self.canvas.update()
            return True
        return False

    # ----------------------------------------------------------------
    # 请求与回调
    # ----------------------------------------------------------------

    def _add_point(self, image_point: QPointF, label: int) -> None:
        # 缺陷模式下,正点必须落在父框内
        if self.sam_state.target_defect and label == 1:
            parent_idx = self.sam_state.target_parent_index
            if 0 <= parent_idx < len(self.canvas.annotations):
                parent = self.canvas.annotations[parent_idx]
                if not parent.contains(image_point.x(), image_point.y()):
                    return
        self.sam_state.points.append((image_point.x(), image_point.y()))
        self.sam_state.labels.append(label)
        self._submit_points()

    def _submit_box(self, x1: float, y1: float, x2: float, y2: float) -> None:
        if self.controller is None:
            return
        image_id = str(self.mw.image_paths[self.mw.current_index]) if self.mw.current_index >= 0 else ""
        self.controller.submit(SamRequest(kind="box", bbox=(x1, y1, x2, y2), image_id=image_id))

    def _submit_points(self) -> None:
        if self.controller is None or not self.sam_state.points:
            return
        image_id = str(self.mw.image_paths[self.mw.current_index]) if self.mw.current_index >= 0 else ""
        self.controller.submit(SamRequest(
            kind="points",
            points=list(self.sam_state.points),
            labels=list(self.sam_state.labels),
            image_id=image_id,
        ))

    def _on_mask_ready(self, polygon, image_id: str) -> None:
        cur_id = str(self.mw.image_paths[self.mw.current_index]) if self.mw.current_index >= 0 else ""
        if image_id and image_id != cur_id:
            return
        self.sam_state.preview_polygon = polygon
        self.canvas.update()

    def _on_failed(self, msg: str) -> None:
        self.log_message.emit(f"SAM 错误:{msg.splitlines()[0] if msg else '(空)'}")

    def _on_busy_changed(self, busy: bool) -> None:
        if hasattr(self, "status_label"):
            if busy:
                self.status_label.setText("推理中…")
            elif self.controller is not None:
                self.status_label.setText(f"已加载:{Path(self.weights_edit.text()).name}")

    # ----------------------------------------------------------------
    # 接受预览
    # ----------------------------------------------------------------

    def _accept_preview(self) -> None:
        if not self.is_active():
            return
        polygon = self.sam_state.preview_polygon
        if not polygon or len(polygon) < 3:
            return
        # 导入主模块的 Annotation / DefectAnnotation
        Annotation = self._get_annotation_cls()
        if self.sam_state.target_defect:
            self._accept_as_defect(polygon)
        else:
            ann = Annotation.from_polygon(self.canvas.current_cls, polygon)
            self.canvas.annotations.append(ann)
            self.canvas.select(len(self.canvas.annotations) - 1)
            self.canvas.annotations_changed.emit()
            self.log_message.emit(f"SAM 添加分割:{len(polygon)} 顶点")
        # 重置准备下一次
        self.sam_state.preview_polygon = None
        self.sam_state.points = []
        self.sam_state.labels = []
        self.canvas.update()

    def _accept_as_defect(self, polygon: list[tuple[float, float]]) -> None:
        parent_idx = self.sam_state.target_parent_index
        if not (0 <= parent_idx < len(self.canvas.annotations)):
            return
        parent = self.canvas.annotations[parent_idx]
        # 把 polygon 裁剪到父框内(简单版:剔除外部点;复杂版可做多边形与父框的布尔交)
        clipped = [(x, y) for x, y in polygon if parent.contains(x, y)]
        if len(clipped) < 3:
            self.log_message.emit("SAM 缺陷:mask 几乎落在目标外,已丢弃")
            return
        DefectAnnotation = self._get_defect_cls()
        defect_type = self.canvas.current_defect_type
        severity = self.canvas.current_defect_severity
        note = self.canvas.current_defect_note
        defect = DefectAnnotation.from_polygon(parent_idx, parent, defect_type, severity, clipped, note)
        self.canvas.defects.append(defect)
        self.canvas.select_defect(len(self.canvas.defects) - 1)
        self.canvas.defects_changed.emit()
        self.log_message.emit(f"SAM 添加缺陷:{len(clipped)} 顶点")

    def _get_annotation_cls(self):
        from cvds_annotation_tool_v2 import Annotation
        return Annotation

    def _get_defect_cls(self):
        from cvds_annotation_tool_v2 import DefectAnnotation
        return DefectAnnotation

    # ----------------------------------------------------------------
    # 绘制(由 ImageCanvas.paintEvent 末尾调用)
    # ----------------------------------------------------------------

    def paint(self, painter: QPainter) -> None:
        if not self.is_active():
            return
        canvas = self.canvas
        st = self.sam_state

        # 拉框中
        if st.drawing_box and st.box_start and st.box_current:
            painter.setPen(QPen(SAM_BOX_COLOR, 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            x1 = st.box_start.x()
            y1 = st.box_start.y()
            x2 = st.box_current.x()
            y2 = st.box_current.y()
            left, right = sorted([x1, x2])
            top, bottom = sorted([y1, y2])
            tl = canvas.image_to_widget(left, top)
            br = canvas.image_to_widget(right, bottom)
            painter.drawRect(QRectF(tl, br))

        # 预览 polygon
        if st.preview_polygon:
            pts = [canvas.image_to_widget(x, y) for x, y in st.preview_polygon]
            poly = QPolygonF(pts)
            fill = QColor(SAM_PREVIEW_COLOR)
            fill.setAlpha(70)
            painter.setBrush(fill)
            painter.setPen(QPen(SAM_PREVIEW_COLOR, 2))
            painter.drawPolygon(poly)

        # 提示点
        for (px, py), label in zip(st.points, st.labels):
            wp = canvas.image_to_widget(px, py)
            color = SAM_POS_POINT_COLOR if label == 1 else SAM_NEG_POINT_COLOR
            painter.setBrush(color)
            painter.setPen(QPen(QColor("#0b0f16"), 2))
            painter.drawEllipse(wp, 7, 7)

        # 角标
        painter.setPen(QColor("#22c55e"))
        target_text = "缺陷" if st.target_defect else "目标"
        hint = f"SAM 模式 · 输出到{target_text}"
        if st.target_defect and st.target_parent_index >= 0:
            hint += f" #{st.target_parent_index + 1}"
        painter.drawText(QRectF(8, 30, 400, 20), Qt.AlignLeft, hint)

    # ----------------------------------------------------------------
    # canvas 方法 patch
    # ----------------------------------------------------------------

    def _patch_canvas_methods(self) -> None:
        """劫持 ImageCanvas 的鼠标和绘制方法,让 SAM 优先处理。"""
        canvas = self.canvas
        integration = self

        original_press = canvas.mousePressEvent
        original_move = canvas.mouseMoveEvent
        original_release = canvas.mouseReleaseEvent
        original_paint = canvas.paintEvent
        original_rollback = canvas.rollback_current_action

        def new_press(event):
            if integration.is_active():
                pt = canvas.widget_to_image(event.position())
                if integration.handle_mouse_press(event, pt):
                    return
            original_press(event)

        def new_move(event):
            if integration.is_active():
                pt = canvas.widget_to_image(event.position())
                if integration.handle_mouse_move(event, pt):
                    return
            original_move(event)

        def new_release(event):
            if integration.is_active():
                pt = canvas.widget_to_image(event.position())
                if integration.handle_mouse_release(event, pt):
                    return
            original_release(event)

        def new_paint(event):
            original_paint(event)
            if integration.is_active():
                painter = QPainter(canvas)
                painter.setRenderHint(QPainter.Antialiasing, True)
                integration.paint(painter)

        def new_rollback():
            if integration.handle_rollback():
                return True
            return original_rollback()

        canvas.mousePressEvent = new_press
        canvas.mouseMoveEvent = new_move
        canvas.mouseReleaseEvent = new_release
        canvas.paintEvent = new_paint
        canvas.rollback_current_action = new_rollback


# ========================================================================
# 主入口:一行接入
# ========================================================================


def install_sam_into_main_window(main_window, insert_before_widget=None) -> SamIntegration:
    """在主窗口构建完成后调用,完成所有集成工作。

    Args:
        main_window: MainWindow 实例(已完成 build_left_panel / build_right_panel)
        insert_before_widget: 把 SAM UI box 插入到这个 widget 之前,可选

    Returns:
        SamIntegration 实例,主窗口建议保存它以便 closeEvent 调用 shutdown
    """
    integration = SamIntegration(main_window)
    integration.attach_ui_to_left_panel(insert_before_widget=insert_before_widget)
    integration.log_message.connect(main_window.append_log)

    # 在 mode_combo 增加 SAM 项
    if main_window.mode_combo.findText(SAM_MODE_NAME) < 0:
        main_window.mode_combo.addItem(SAM_MODE_NAME)

    # 包装 on_mode_changed
    original_on_mode_changed = main_window.on_mode_changed

    def new_on_mode_changed(idx: int) -> None:
        text = main_window.mode_combo.itemText(idx)
        if text == SAM_MODE_NAME:
            # 进入 SAM 模式:画布底层 mode 设为 polygon(影响 data.yaml 的 task)
            main_window.canvas.set_mode("polygon")
            integration.activate(for_defect=False)
            # 还是要写一次 yaml
            from cvds_annotation_tool_v2 import write_data_yaml
            write_data_yaml(main_window.output_root(), main_window.labels(), task="segment")
            return
        # 离开 SAM 模式
        if integration.is_active():
            integration.deactivate()
        original_on_mode_changed(idx)

    main_window.on_mode_changed = new_on_mode_changed
    main_window.mode_combo.currentIndexChanged.disconnect()
    main_window.mode_combo.currentIndexChanged.connect(new_on_mode_changed)

    # 包装 goto_image:切图时通知 SAM 更新 image
    original_goto_image = main_window.goto_image

    def new_goto_image(row: int) -> None:
        original_goto_image(row)
        integration.on_image_changed()

    main_window.goto_image = new_goto_image

    # 包装 closeEvent:确保线程退出
    original_close = main_window.closeEvent

    def new_close(event):
        try:
            integration.shutdown()
        except Exception:  # noqa: BLE001
            pass
        original_close(event)

    main_window.closeEvent = new_close

    return integration
