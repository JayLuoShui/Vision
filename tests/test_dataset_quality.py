import json

from cvds_annotation_tool.services.dataset_quality import audit_dataset


def test_dataset_quality_finds_invalid_orphan_and_defect_errors(tmp_path):
    root = tmp_path / "dataset"
    (root / "images" / "train").mkdir(parents=True)
    (root / "labels" / "train").mkdir(parents=True)
    (root / "defects" / "train").mkdir(parents=True)
    (root / "images" / "train" / "a.jpg").write_bytes(b"fake")
    (root / "images" / "train" / "empty.jpg").write_bytes(b"fake")
    (root / "images" / "train" / "missing.jpg").write_bytes(b"fake")
    (root / "labels" / "train" / "a.txt").write_text("0 1.2 0.5 0.1 0.1\nbad line\n", encoding="utf-8")
    (root / "labels" / "train" / "empty.txt").write_text("", encoding="utf-8")
    (root / "labels" / "train" / "orphan.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    (root / "defects" / "train" / "a.json").write_text(
        json.dumps({"defects": [{"parent_index": 3, "parent_cls": 0, "kind": "point", "points": [[0.5, 0.5]]}]}),
        encoding="utf-8",
    )

    report = audit_dataset(root)

    assert report.total_images == 3
    assert report.empty_label_images == 1
    assert report.missing_labels == 1
    assert report.orphan_labels == 1
    assert report.invalid_yolo_lines == 1
    assert report.out_of_bounds_coords == 1
    assert report.invalid_defects == 1
    assert report.report_json.exists()
    assert report.class_distribution_csv.exists()
