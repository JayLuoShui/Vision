"""CVDS PySide6 UI mock：交互调整 QSS，并用 QWidget.grab() 自动截图。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QTimer, Qt
from PySide6.QtGui import QFont, QFontDatabase, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


HERE = Path(__file__).resolve().parent
QSS_PATH = HERE / "cvds.qss"
DEFAULT_CAPTURE = HERE / "preview.png"
REFERENCE_IMAGE = HERE / "reference_dashboard.png"
_FONT_FAMILY = ""


def load_ui_font() -> str:
    global _FONT_FAMILY
    if _FONT_FAMILY:
        return _FONT_FAMILY
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if not font_path.is_file():
        return ""
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    families = QFontDatabase.applicationFontFamilies(font_id)
    _FONT_FAMILY = families[0] if families else ""
    if _FONT_FAMILY:
        QApplication.instance().setFont(QFont(_FONT_FAMILY))
    return _FONT_FAMILY


def button(text: str, name: str = "") -> QPushButton:
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    return widget


def field(text: str = "", width: int = 176) -> QLineEdit:
    widget = QLineEdit(text)
    widget.setFixedWidth(width)
    return widget


def form() -> QFormLayout:
    layout = QFormLayout()
    layout.setContentsMargins(8, 10, 8, 8)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(8)
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
    return layout


class PreviewWindow(QMainWindow):
    def __init__(self, output_path: Path = DEFAULT_CAPTURE) -> None:
        super().__init__()
        load_ui_font()
        self.output_path = Path(output_path)
        self.setWindowTitle("CVDS UI 实时调整 · PySide6 Mock")
        self.resize(2100, 914)
        self.setMinimumSize(1500, 800)

        self.mock_root = QWidget(objectName="dashboardRoot")
        root_layout = QVBoxLayout(self.mock_root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)
        root_layout.addWidget(self._build_brand())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        self.sidebar = self._build_sidebar()
        self.sidebar.setFixedWidth(320)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self._build_workspace())
        splitter.setSizes([320, 1040])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, 1)
        self.sidebar.hide()
        self.setCentralWidget(self.mock_root)

        self._build_editor()
        self._reload_qss()

        self.apply_timer = QTimer(self, interval=250, singleShot=True)
        self.apply_timer.timeout.connect(self._apply_editor_qss)
        self.editor.textChanged.connect(self.apply_timer.start)

        self.watcher = QFileSystemWatcher([str(QSS_PATH)], self)
        self.watcher.fileChanged.connect(self._reload_qss)
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save_qss)

    def _build_brand(self) -> QFrame:
        bar = QFrame(objectName="brandBar")
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 5, 10, 5)
        mark = QLabel(objectName="brandMark")
        mark.setFixedSize(32, 32)
        mark.setPixmap(
            QPixmap(str(HERE.parent / "cvds_cpp_detector" / "assets" / "cogy_mark.png")).scaled(
                mark.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        )
        title = QLabel("氪技 COGY · CVDS ONLINE PARCEL FLOW MONITOR", objectName="AppTitle")
        subtitle = QLabel("在线包裹流量监测", objectName="brandSubtitle")
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        layout.addWidget(mark)
        layout.addLayout(titles)
        layout.addStretch()
        layout.addWidget(QLabel("●  video_20260513_152237.mp4", objectName="onlineBadge"))
        layout.addWidget(QLabel("本地文件", objectName="channelStatus"))
        layout.addWidget(QLabel("2026-06-29 17:01:01", objectName="runtimeClock"))
        layout.addWidget(QLabel("V2.4.1", objectName="versionBadge"))
        self.top_control_button = button("^  收起控制面板", "topControlButton")
        self.top_control_button.setFixedWidth(120)
        self.top_control_button.setFixedHeight(40)
        layout.addWidget(self.top_control_button)
        layout.addWidget(QLabel("●  系统就绪", objectName="readyBadge"))
        return bar

    def _build_sidebar(self) -> QWidget:
        shell = QWidget(objectName="settingsPanel")
        shell.setMinimumWidth(320)
        shell.setMaximumWidth(320)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget(objectName="sidebarHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 10, 7)
        header_layout.setSpacing(1)
        header_layout.addWidget(QLabel("控制面板", objectName="sidebarTitle"))
        header_layout.addWidget(QLabel("SYSTEM PARAMETERS", objectName="SideSubtitle"))
        layout.addWidget(header)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._video_page())
        self.pages.addWidget(self._inference_page())
        self.pages.addWidget(self._roi_page())
        self.pages.addWidget(self._control_page())

        self.nav_buttons: list[QPushButton] = []
        nav = QWidget(objectName="SideMenu")
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)
        for index, text in enumerate(("▣  视频源", "◉  推理参数", "⌗  ROI 区域", "▥  检测控制")):
            item = button(text, "navButton")
            item.setCheckable(True)
            item.setAutoExclusive(True)
            item.clicked.connect(lambda _checked=False, i=index: self.pages.setCurrentIndex(i))
            item.clicked.connect(self._sync_nav)
            nav_layout.addWidget(item)
            self.nav_buttons.append(item)
        self.nav_buttons[0].setChecked(True)
        layout.addWidget(nav)

        scroll = QScrollArea(objectName="settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(objectName="settingsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(6, 5, 6, 5)
        content_layout.addWidget(self.pages)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        dock = QWidget(objectName="actionDock")
        dock_layout = QVBoxLayout(dock)
        dock_layout.setContentsMargins(6, 6, 6, 6)
        dock_layout.setSpacing(5)
        dock_layout.addWidget(button("开始检测", "primaryButton"))
        dock_layout.addWidget(button("停止检测", "dangerButton"))
        layout.addWidget(dock)
        return shell

    def _sync_nav(self) -> None:
        for index, item in enumerate(self.nav_buttons):
            item.setChecked(index == self.pages.currentIndex())

    def _page(self, group: QGroupBox) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)
        layout.addStretch()
        return page

    def _video_page(self) -> QWidget:
        group = QGroupBox("视频源")
        layout = form()
        source = QComboBox()
        source.addItems(["视频流", "本地文件"])
        source.setFixedWidth(176)
        layout.addRow("来源类型", source)
        multi = QPlainTextEdit("多路视频在线检测：每行一路本地视频或 RTSP 地址")
        multi.setFixedSize(176, 68)
        layout.addRow("多路视频源", multi)
        layout.addRow("设备IP", field("192.168.10.254"))
        layout.addRow("RTSP端口", field("554", 68))
        layout.addRow("登录账号", field("admin"))
        password = field("123456789")
        password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("登录密码", password)
        channel = QSpinBox()
        channel.setRange(1, 64)
        channel.setValue(19)
        channel.setFixedWidth(176)
        layout.addRow("通道", channel)
        stream = QComboBox()
        stream.addItems(["主码流", "子码流"])
        stream.setFixedWidth(176)
        layout.addRow("码流", stream)
        layout.addRow("多路通道", field("4, 13, 19"))
        protocol = QComboBox()
        protocol.addItems(["TCP", "UDP"])
        protocol.setFixedWidth(176)
        layout.addRow("传输协议", protocol)
        actions = QHBoxLayout()
        actions.addWidget(button("应用视频流"))
        actions.addWidget(button("测试连接"))
        layout.addRow(actions)
        group.setLayout(layout)
        return self._page(group)

    def _inference_page(self) -> QWidget:
        group = QGroupBox("推理参数")
        layout = form()
        model = QPlainTextEdit("yolo26s-seg-wds-1024-best_int8_openvino_model")
        model.setFixedSize(176, 50)
        model.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addRow("视觉模型", model)
        layout.addRow("选择方式", button("模型文件 / OpenVINO目录"))
        for label, values in (
            ("推理后端", ["OpenVINO"]),
            ("类别", ["全部类别"]),
            ("执行设备", ["AUTO", "CPU", "GPU"]),
        ):
            combo = QComboBox()
            combo.addItems(values)
            combo.setFixedWidth(176)
            layout.addRow(label, combo)
        for label, value in (("输入尺寸", 1024), ("预览FPS", 60)):
            spin = QSpinBox()
            spin.setRange(1, 4096)
            spin.setValue(value)
            spin.setFixedWidth(150)
            layout.addRow(label, spin)
        for label, value in (("置信度", 0.60), ("NMS IoU", 0.45)):
            spin = QDoubleSpinBox()
            spin.setRange(0, 1)
            spin.setSingleStep(0.05)
            spin.setValue(value)
            spin.setFixedWidth(150)
            layout.addRow(label, spin)
        group.setLayout(layout)
        return self._page(group)

    def _roi_page(self) -> QWidget:
        group = QGroupBox("流量监测")
        layout = form()
        for label, value in (
            ("当前区域", "主统计区域"),
            ("区域名称", "主统计区域"),
            ("当前区域ROI", "左键加点，右键完成"),
            ("检测区域", "可选，只在该多边形区域检测"),
            ("计数口径", "主统计区域"),
        ):
            layout.addRow(label, field(value, 176))
        seconds = QSpinBox()
        seconds.setValue(5)
        seconds.setFixedWidth(120)
        layout.addRow("堵包判定秒", seconds)
        checks = QHBoxLayout()
        checks.addWidget(QCheckBox("参与累计"))
        checks.addWidget(QCheckBox("启用堵包"))
        layout.addRow(checks)
        for labels in (("新增区域", "重命名区域", "删除区域"), ("绘制流量ROI", "绘制检测区域"), ("撤回ROI点", "清空当前ROI"), ("保存区域配置", "加载区域配置")):
            row = QHBoxLayout()
            for text in labels:
                row.addWidget(button(text))
            layout.addRow(row)
        group.setLayout(layout)
        return self._page(group)

    def _control_page(self) -> QWidget:
        group = QGroupBox("检测控制")
        layout = form()
        layout.addRow("输出目录", field("runs", 176))
        choose = button("选择输出目录")
        choose.setFixedWidth(176)
        check = button("运行环境自检")
        check.setFixedWidth(176)
        layout.addRow("", choose)
        layout.addRow("", check)
        group.setLayout(layout)
        return self._page(group)

    def _build_workspace(self) -> QWidget:
        workspace = QWidget(objectName="monitorWorkspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        strip = QWidget(objectName="dashboardStrip")
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(4)
        for title, value, value_name, status in (
            ("累计包裹", "1286", "KpiValue", None),
            ("系统状态", "已完成", "KpiStatusMain", "completed"),
            ("当前区域状态", "区域1 待机\n区域2 待机", "KpiStatusMain", "idle"),
            ("堵包次数", "3", "KpiValue", "jam"),
        ):
            card = QFrame(objectName="dashboardCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 7, 12, 7)
            card_layout.setSpacing(1)
            title_label = QLabel(title, objectName="KpiTitle")
            value_label = QLabel(value, objectName=value_name)
            if status:
                value_label.setProperty("status", status)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addStretch()
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            card_layout.addStretch()
            strip_layout.addWidget(card)
        strip.setFixedHeight(94)
        layout.addWidget(strip)

        monitor = QFrame(objectName="monitorPanel")
        monitor_layout = QVBoxLayout(monitor)
        monitor_layout.setContentsMargins(0, 0, 0, 0)
        monitor_layout.setSpacing(0)
        header = QFrame(objectName="monitorHeader")
        header.setFixedHeight(34)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 10, 0)
        header_layout.addWidget(QLabel("实时监控画面", objectName="PanelTitle"))
        header_layout.addStretch()
        header_layout.addWidget(QLabel("ROI 可视化 · 实时检测", objectName="sectionHint"))
        reference = QPixmap(str(REFERENCE_IMAGE))
        if reference.isNull():
            raise RuntimeError(f"无法加载参考监控图：{REFERENCE_IMAGE}")
        surface = QWidget(objectName="videoSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(2, 0, 2, 0)
        surface_layout.setSpacing(0)
        surface_layout.addSpacing(48)
        camera_grid = QWidget(objectName="CameraGrid")
        camera_grid.setFixedHeight(486)
        camera_layout = QHBoxLayout(camera_grid)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        camera_layout.setSpacing(4)
        for crop, stretch in (((15, 274, 855, 486), 52), ((873, 274, 786, 486), 48)):
            camera = QLabel(objectName="CameraView")
            camera.setPixmap(reference.copy(*crop))
            camera.setScaledContents(True)
            camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
            camera_layout.addWidget(camera, stretch)
        surface_layout.addWidget(camera_grid)
        surface_layout.addStretch()
        monitor_layout.addWidget(header)
        monitor_layout.addWidget(surface, 1)
        layout.addWidget(monitor, 1)

        region = QFrame(objectName="regionPanel")
        region.setFixedHeight(46)
        region_layout = QHBoxLayout(region)
        region_layout.setContentsMargins(10, 0, 6, 0)
        region_layout.addWidget(QLabel("区域统计详情", objectName="PanelTitle"))
        region_layout.addStretch()
        region_layout.addWidget(button("展开区域统计   ›", "footerToggleButton"))
        region_layout.addWidget(button("展开运行日志   ›", "footerToggleButton"))
        layout.addWidget(region)
        return workspace

    def _build_editor(self) -> None:
        dock = QDockWidget("实时 stylesheet 调整", self)
        dock.setObjectName("styleEditorDock")
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        hint = QLabel("修改后停顿 250ms 自动应用并截图；Ctrl+S 保存到 cvds.qss。")
        hint.setWordWrap(True)
        self.editor = QPlainTextEdit(objectName="styleEditor")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        actions = QHBoxLayout()
        actions.addWidget(button("重新载入"))
        actions.itemAt(0).widget().clicked.connect(self._reload_qss)
        actions.addWidget(button("保存 QSS 并截图", "primaryButton"))
        actions.itemAt(1).widget().clicked.connect(self.save_qss)
        self.capture_label = QLabel()
        self.capture_label.setWordWrap(True)
        layout.addWidget(hint)
        layout.addWidget(self.editor, 1)
        layout.addLayout(actions)
        layout.addWidget(self.capture_label)
        dock.setWidget(panel)
        dock.setMinimumWidth(420)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _reload_qss(self) -> None:
        text = QSS_PATH.read_text(encoding="utf-8")
        if self.editor.toPlainText() != text:
            self.editor.blockSignals(True)
            self.editor.setPlainText(text)
            self.editor.blockSignals(False)
        self._apply_editor_qss()
        if hasattr(self, "watcher") and str(QSS_PATH) not in self.watcher.files():
            self.watcher.addPath(str(QSS_PATH))

    def _apply_editor_qss(self) -> None:
        QApplication.instance().setStyleSheet(self.editor.toPlainText())
        QTimer.singleShot(0, self.capture)

    def save_qss(self) -> None:
        QSS_PATH.write_text(self.editor.toPlainText(), encoding="utf-8")
        self._apply_editor_qss()

    def capture(self) -> bool:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        saved = self.mock_root.grab().save(str(self.output_path), "PNG")
        self.capture_label.setText(f"预览：{self.output_path}")
        return saved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--capture-only", action="store_true")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = PreviewWindow(args.out)
    window.show()
    if args.capture_only:
        QTimer.singleShot(300, lambda: (window.capture(), app.quit()))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
