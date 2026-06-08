from pathlib import Path
import os
import subprocess
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from apps.cvds_annotation_tool_v2 import (  # noqa: E402
    Annotation,
    MainWindow,
    VSCODE_DARK_QSS,
    label_path_for_image_path,
    read_data_yaml_labels,
)
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402


def get_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_box_annotation_roundtrip():
    ann = Annotation.from_box(1, 40, 25, 60, 55)

    line = ann.to_yolo_line(width=100, height=100)
    parsed = Annotation.from_yolo_line(line, width=100, height=100)

    assert parsed is not None
    assert parsed.cls == 1
    assert parsed.kind == "box"
    assert tuple(round(value, 6) for value in parsed.box_corners()) == (40.0, 25.0, 60.0, 55.0)


def test_polygon_annotation_roundtrip():
    ann = Annotation.from_polygon(0, [(10, 20), (40, 20), (30, 60)])

    line = ann.to_yolo_line(width=100, height=100)
    parsed = Annotation.from_yolo_line(line, width=100, height=100)

    assert parsed is not None
    assert parsed.cls == 0
    assert parsed.kind == "polygon"
    assert parsed.points == [(10.0, 20.0), (40.0, 20.0), (30.0, 60.0)]


def test_read_data_yaml_labels_from_dict(tmp_path):
    (tmp_path / "data.yaml").write_text("names:\n  0: parcel\n  1: bag\n", encoding="utf-8")

    assert read_data_yaml_labels(tmp_path) == ["parcel", "bag"]


def test_label_path_for_yolo_output_image_uses_original_stem(tmp_path):
    output_dir = tmp_path / "dataset"
    image_path = output_dir / "images" / "train" / "frame 001.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")

    label_path = label_path_for_image_path(image_path, output_dir)

    assert label_path == output_dir / "labels" / "train" / "frame 001.txt"


def test_v2_layout_and_theme_contract():
    get_qapp()
    window = MainWindow()

    assert window.left_shell.minimumWidth() >= 560
    assert window.left_shell.maximumWidth() <= 720
    assert window.splitter.childrenCollapsible() is False
    assert window.right_shell.sizePolicy().horizontalStretch() > window.left_shell.sizePolicy().horizontalStretch()
    assert "QComboBox::drop-down" in VSCODE_DARK_QSS
    assert "border-left" in VSCODE_DARK_QSS
    assert "#4ec9b0" in VSCODE_DARK_QSS
    assert "#d7ba7d" in VSCODE_DARK_QSS


def test_delete_current_frame_keeps_neighbor_selection(tmp_path):
    get_qapp()
    window = MainWindow()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    image_paths = []
    for idx in range(3):
        path = source_dir / f"frame_{idx}.jpg"
        image = QImage(8, 8, QImage.Format_RGB32)
        image.fill(0xFF202020)
        assert image.save(str(path))
        image_paths.append(path)
    window.output_edit.setText(str(tmp_path / "dataset"))
    window.full_paths = list(image_paths)
    window.full_box_counts = [0, 0, 0]
    window.image_paths = list(image_paths)
    window.image_model.set_paths(image_paths, [0, 0, 0])
    window.goto_index(1)
    get_qapp().processEvents()
    original_question = QMessageBox.question
    QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    try:
        window.delete_current_frame()
        get_qapp().processEvents()
    finally:
        QMessageBox.question = original_question

    assert [path.name for path in window.image_paths] == ["frame_0.jpg", "frame_2.jpg"]
    assert window.current_index == 1
    assert window.image_list.currentIndex().row() == 1
    window.step_image(-1)
    assert window.current_index == 0


def test_escape_rolls_back_last_polygon_point():
    get_qapp()
    window = MainWindow()
    canvas = window.canvas
    canvas.image_size = (100, 100)
    canvas.drawing_polygon = True
    canvas.polygon_points = [(10, 10), (20, 20), (30, 30)]
    canvas.polygon_cursor = QPointF(30, 30)

    event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    canvas.keyPressEvent(event)

    assert canvas.drawing_polygon is True
    assert canvas.polygon_points == [(10, 10), (20, 20)]


def test_startup_keeps_heavy_image_libs_lazy():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    script = (
        "import sys;"
        "import apps.cvds_annotation_tool_v2;"
        "print('cv2' in sys.modules, 'numpy' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )

    assert result.stdout.strip() == "False False"


if __name__ == "__main__":
    import tempfile

    test_box_annotation_roundtrip()
    test_polygon_annotation_roundtrip()
    with tempfile.TemporaryDirectory() as temp_dir:
        test_read_data_yaml_labels_from_dict(Path(temp_dir))
    with tempfile.TemporaryDirectory() as temp_dir:
        test_label_path_for_yolo_output_image_uses_original_stem(Path(temp_dir))
    test_v2_layout_and_theme_contract()
    with tempfile.TemporaryDirectory() as temp_dir:
        test_delete_current_frame_keeps_neighbor_selection(Path(temp_dir))
    test_escape_rolls_back_last_polygon_point()
    test_startup_keeps_heavy_image_libs_lazy()
    print("8 passed")
