from __future__ import annotations

from dws_validator.labels import count_yolo_instances


def test_empty_txt_returns_zero(tmp_path):
    label = tmp_path / "empty.txt"
    label.write_text("", encoding="utf-8")

    assert count_yolo_instances(label) == 0


def test_yolo_segmentation_rows_return_count(tmp_path):
    label = tmp_path / "sample.txt"
    label.write_text(
        "0 0.1 0.1 0.2 0.1 0.2 0.2\n"
        "0 0.3 0.3 0.4 0.3 0.4 0.4\n",
        encoding="utf-8",
    )

    assert count_yolo_instances(label) == 2


def test_missing_label_returns_none(tmp_path):
    assert count_yolo_instances(tmp_path / "missing.txt") is None


def test_comment_and_invalid_lines_are_skipped(tmp_path):
    label = tmp_path / "sample.txt"
    label.write_text(
        "# comment\n"
        "\n"
        "not-a-number 0.1 0.1 0.2 0.2\n"
        "0 0.5 0.5 0.2 0.2\n",
        encoding="utf-8",
    )

    assert count_yolo_instances(label) == 1
