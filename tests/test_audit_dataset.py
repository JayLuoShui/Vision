import csv
import shutil
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_dataset import audit_dataset, group_id_for_image  # noqa: E402


class DatasetAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self._testMethodName)
        self.dataset = self.root / "dataset"
        self.output = self.root / "audit"
        self.dataset.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root)

    def write_image(self, split: str, name: str) -> Path:
        path = self.dataset / "images" / split / name
        path.parent.mkdir(parents=True, exist_ok=True)
        img = np.full((100, 100, 3), 240, dtype=np.uint8)
        cv2.imwrite(str(path), img)
        return path

    def write_label(self, split: str, name: str, lines: list[str]) -> Path:
        path = self.dataset / "labels" / split / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return path

    def test_audits_large_boxes_empty_samples_and_group_leakage(self) -> None:
        self.write_image("train", "videoA_000001.jpg")
        self.write_label("train", "videoA_000001.txt", ["0 0.5 0.5 0.5 0.5"])
        self.write_image("val", "videoA_000002.jpg")
        self.write_label("val", "videoA_000002.txt", ["0 0.5 0.5 0.7 0.7"])
        self.write_image("test", "videoB_000001.jpg")
        self.write_label("test", "videoB_000001.txt", [])

        summary = audit_dataset(
            dataset=self.dataset,
            output=self.output,
            large_threshold=0.2,
            huge_threshold=0.4,
            sample_empty=1,
            seed=7,
            group_mode="video-id",
            group_prefix_parts=2,
            group_regex=None,
        )

        stats_path = self.output / "bbox_area_stats.csv"
        with stats_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))

        self.assertEqual(summary.total_images, 3)
        self.assertEqual(summary.annotated_images, 2)
        self.assertEqual(summary.empty_label_images, 1)
        self.assertEqual(summary.total_bboxes, 2)
        self.assertEqual(summary.large_bbox_count, 2)
        self.assertEqual(summary.huge_bbox_count, 1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["bbox_xywh"], "0.500000 0.500000 0.500000 0.500000")
        self.assertAlmostEqual(float(rows[0]["area_ratio"]), 0.25)
        self.assertTrue((self.output / "large_bbox_over_20" / "images" / "train" / "videoA_000001.jpg").exists())
        self.assertTrue((self.output / "large_bbox_over_40" / "images" / "val" / "videoA_000002.jpg").exists())
        self.assertTrue((self.output / "negative_samples" / "images" / "test" / "videoB_000001.jpg").exists())
        self.assertTrue((self.output / "dataset_quality_report.md").exists())
        self.assertTrue((self.output / "group_split_leakage.csv").exists())
        self.assertTrue((self.output / "group_split_suggestion.csv").exists())
        self.assertEqual(summary.leakage_group_count, 1)

    def test_video_id_group_removes_trailing_frame_number(self) -> None:
        image = Path("images/train/crossbelt_mkv_000246.jpg")
        self.assertEqual(group_id_for_image(image, "video-id", 2, None), "crossbelt_mkv")


if __name__ == "__main__":
    unittest.main()
