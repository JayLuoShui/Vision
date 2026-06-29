import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


MOCKUP_DIR = Path(__file__).parents[1] / "apps" / "cvds_ui_mockup"
sys.path.insert(0, str(MOCKUP_DIR))

from qt_preview import REFERENCE_IMAGE, PreviewWindow, load_ui_font  # noqa: E402


def test_reference_dashboard_layout_matches_the_target_monitor_view():
    assert REFERENCE_IMAGE.is_file()
    app = QApplication.instance() or QApplication([])
    window = PreviewWindow()
    window.show()
    app.processEvents()

    assert window.sidebar.isHidden()
    assert window.mock_root.height() == 914
    assert window.top_control_button.text() == "^  收起控制面板"
    assert window.top_control_button.width() == 120
    assert window.top_control_button.height() == 40
    assert window.findChild(QWidget, "brandBar").height() == 52
    assert window.findChild(QWidget, "dashboardStrip").height() == 94
    assert window.findChild(QWidget, "regionPanel").height() == 46
    assert len(window.findChildren(QLabel, "CameraView")) == 2
    assert [label.text() for label in window.findChildren(QLabel, "KpiValue")] == ["1286", "3"]
    assert window.findChild(QLabel, "onlineBadge").text() == "●  video_20260513_152237.mp4"
    qss = (MOCKUP_DIR / "cvds.qss").read_text(encoding="utf-8")
    assert '#KpiValue[status="jam"]' in qss
    window.close()


def test_kpi_text_is_centered_with_balanced_sizes():
    app = QApplication.instance() or QApplication([])
    window = PreviewWindow()
    window.show()
    app.processEvents()

    titles = window.findChildren(QLabel, "KpiTitle")
    values = window.findChildren(QLabel, "KpiValue")
    statuses = window.findChildren(QLabel, "KpiStatusMain")
    assert all(label.alignment() == Qt.AlignmentFlag.AlignCenter for label in titles + values + statuses)
    assert {label.font().pixelSize() for label in titles} == {13}
    assert {label.font().pixelSize() for label in values} == {24}
    assert {label.font().pixelSize() for label in statuses} == {16}
    window.close()


def test_kpi_statuses_have_semantic_colors():
    app = QApplication.instance() or QApplication([])
    window = PreviewWindow()
    statuses = window.findChildren(QLabel, "KpiStatusMain")
    assert {label.property("status") for label in statuses} == {"idle", "completed"}

    qss = (MOCKUP_DIR / "cvds.qss").read_text(encoding="utf-8")
    expected = {
        'status="idle"': "#8FA3B8",
        'status="jam"': "#F25555",
        'status="running"': "#4DA3FF",
        'status="completed"': "#36C98F",
    }
    for selector, color in expected.items():
        assert f'#KpiStatusMain[{selector}]' in qss
        assert color in qss
    app.processEvents()
    window.close()


def test_top_status_controls_share_the_same_font():
    app = QApplication.instance() or QApplication([])
    window = PreviewWindow()
    window.show()
    app.processEvents()

    controls = [
        window.findChild(QLabel, "onlineBadge"),
        window.findChild(QLabel, "versionBadge"),
        window.findChild(QPushButton, "topControlButton"),
        window.findChild(QLabel, "readyBadge"),
    ]
    assert all(controls)
    assert {control.font().pixelSize() for control in controls} == {13}
    assert {control.font().weight() for control in controls} == {500}
    window.close()


def test_kpi_cards_use_requested_values_and_vertical_layout():
    app = QApplication.instance() or QApplication([])
    window = PreviewWindow()

    titles = [label.text() for label in window.findChildren(QLabel, "KpiTitle")]
    values = [label.text() for label in window.findChildren(QLabel, "KpiValue")]
    statuses = [label.text() for label in window.findChildren(QLabel, "KpiStatusMain")]
    cards = window.findChildren(QWidget, "dashboardCard")

    assert titles == ["累计包裹", "系统状态", "当前区域状态", "堵包次数"]
    assert values == ["1286", "3"]
    assert statuses == ["已完成", "区域1 待机\n区域2 待机"]
    assert all(isinstance(card.layout(), QVBoxLayout) for card in cards)
    app.processEvents()
    window.close()


def test_stylesheet_uses_requested_typography_contract():
    qss = (MOCKUP_DIR / "cvds.qss").read_text(encoding="utf-8")
    for selector in (
        "*",
        "#AppTitle",
        "#SideMenu QPushButton",
        "#SideSubtitle",
        "#PanelTitle",
        "#KpiTitle",
        "#KpiValue",
        "#KpiStatusMain",
        "QTableWidget",
        "QHeaderView::section",
    ):
        assert f"{selector} {{" in qss

    app = QApplication.instance() or QApplication([])
    window = PreviewWindow()
    assert window.findChild(QLabel, "AppTitle") is not None
    assert window.findChild(QWidget, "SideMenu") is not None
    assert window.findChild(QLabel, "SideSubtitle") is not None
    assert window.findChild(QLabel, "PanelTitle") is not None
    assert window.findChild(QLabel, "KpiTitle") is not None
    assert window.findChild(QLabel, "KpiValue") is not None
    assert window.findChild(QLabel, "KpiStatusMain") is not None
    app.processEvents()
    window.close()


def test_preview_loads_a_chinese_font_for_headless_capture():
    app = QApplication.instance() or QApplication([])
    assert load_ui_font()
    app.processEvents()


def test_preview_window_can_switch_pages_and_capture(tmp_path):
    app = QApplication.instance() or QApplication([])
    output = tmp_path / "preview.png"
    window = PreviewWindow(output_path=output)

    assert isinstance(window, QMainWindow)
    assert window.sidebar.minimumWidth() == 320
    assert window.sidebar.maximumWidth() == 320
    assert window.pages.count() == 4

    window.nav_buttons[2].click()
    assert window.pages.currentIndex() == 2

    window.show()
    app.processEvents()
    assert window.capture()
    assert output.is_file()
    assert output.stat().st_size > 0

    window.close()
