import json

from cvds_annotation_tool.io.defect_io import read_defects, write_defects
from cvds_annotation_tool.models.annotation import Annotation
from cvds_annotation_tool.models.defect import DefectAnnotation, reindex_defects_after_delete


def test_defect_polygon_box_point_json_roundtrip(tmp_path):
    path = tmp_path / "defects.json"
    parent = Annotation.from_box(2, 0, 0, 100, 100)
    defects = [
        DefectAnnotation.from_polygon(0, parent, "hole", "high", [(1, 2), (3, 4), (5, 6)]),
        DefectAnnotation.from_box(0, parent, "crack", "medium", 10, 20, 30, 40),
        DefectAnnotation.from_point(0, parent, "dent", "low", 50, 60),
    ]

    write_defects(path, defects, width=100, height=100, image_name="a.jpg", labels=["parcel", "x", "box"])
    loaded = read_defects(path, width=100, height=100)

    assert [item.kind for item in loaded] == ["polygon", "box", "point"]
    assert [item.defect_type for item in loaded] == ["hole", "crack", "dent"]


def test_old_defect_json_without_kind_defaults_to_polygon(tmp_path):
    path = tmp_path / "old.json"
    payload = {
        "version": 1,
        "defects": [
            {
                "id": "old1",
                "parent_index": 0,
                "parent_cls": 0,
                "type": "hole",
                "severity": "medium",
                "points": [[0.1, 0.1], [0.2, 0.1], [0.1, 0.2]],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = read_defects(path, width=100, height=100)

    assert len(loaded) == 1
    assert loaded[0].kind == "polygon"


def test_delete_target_reindexes_defect_parent_index():
    parents = [Annotation.from_box(0, 0, 0, 10, 10), Annotation.from_box(1, 20, 20, 40, 40)]
    defects = [
        DefectAnnotation.from_point(0, parents[0], "hole", "low", 1, 1),
        DefectAnnotation.from_point(1, parents[1], "crack", "high", 30, 30),
    ]

    updated = reindex_defects_after_delete(defects, deleted_index=0)

    assert len(updated) == 1
    assert updated[0].parent_index == 0
    assert updated[0].parent_cls == 1
