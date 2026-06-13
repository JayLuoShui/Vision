import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.cvds_annotation_tool import label_path_for_image_path, read_data_yaml_labels  # noqa: E402


class AnnotationYoloLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self._testMethodName)
        self.root.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.root)

    def test_reads_labels_from_yolo_data_yaml_dict_names(self) -> None:
        dataset = self.root / "dataset"
        dataset.mkdir()
        (dataset / "data.yaml").write_text(
            "\n".join(
                [
                    "path: .",
                    "train: images/train",
                    "names:",
                    "  0: parcel",
                    "  1: damaged",
                ]
            ),
            encoding="utf-8",
        )

        self.assertEqual(read_data_yaml_labels(dataset), ["parcel", "damaged"])

    def test_uses_exact_label_name_for_images_inside_yolo_folder(self) -> None:
        dataset = self.root / "dataset"
        image = dataset / "images" / "train" / "cross belt frame 001.jpg"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"")

        label_path = label_path_for_image_path(image, dataset)

        self.assertEqual(label_path, dataset / "labels" / "train" / "cross belt frame 001.txt")


if __name__ == "__main__":
    unittest.main()
