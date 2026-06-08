from cvds_annotation_tool.io.yolo_io import read_yolo_annotations, write_yolo_annotations
from cvds_annotation_tool.models.annotation import Annotation


def test_yolo_box_line_roundtrip(tmp_path):
    path = tmp_path / "label.txt"
    annotations = [Annotation.from_box(1, 10, 20, 110, 220)]

    write_yolo_annotations(path, annotations, width=200, height=400)
    loaded = read_yolo_annotations(path, width=200, height=400)

    assert len(loaded) == 1
    assert loaded[0].kind == "box"
    assert loaded[0].cls == 1
    assert loaded[0].box_corners() == (10.0, 20.0, 110.0, 220.0)


def test_yolo_polygon_line_roundtrip(tmp_path):
    path = tmp_path / "label.txt"
    polygon = [(10, 20), (80, 20), (90, 100), (15, 105)]

    write_yolo_annotations(path, [Annotation.from_polygon(0, polygon)], width=100, height=120)
    loaded = read_yolo_annotations(path, width=100, height=120)

    assert len(loaded) == 1
    assert loaded[0].kind == "polygon"
    assert loaded[0].points == [(10.0, 20.0), (80.0, 20.0), (90.0, 100.0), (15.0, 105.0)]


def test_empty_label_file_counts_as_zero(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")

    assert read_yolo_annotations(path, width=100, height=100) == []
