import shutil
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.augment_yolomask_background import (  # noqa: E402
    apply_background_strategy,
    augment_split,
    build_parcel_mask,
    copy_label_unchanged,
    save_png,
)


class YoloMaskBackgroundAugmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self._testMethodName)
        self.root.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root)

    def test_grayscale_background_preserves_parcel_pixels(self) -> None:
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        image[:, :] = (10, 90, 200)
        image[3:7, 3:7] = (20, 30, 40)
        label_lines = ["0 0.300000 0.300000 0.700000 0.300000 0.700000 0.700000 0.300000 0.700000"]
        mask = build_parcel_mask(label_lines, image.shape[:2])

        augmented = apply_background_strategy(image, mask, "grayscale", np.random.default_rng(1), [])

        self.assertTrue(np.array_equal(augmented[mask], image[mask]))
        self.assertFalse(np.array_equal(augmented[~mask], image[~mask]))

    def test_background_crop_uses_negative_image_and_copies_label_text(self) -> None:
        image = np.zeros((6, 6, 3), dtype=np.uint8)
        image[:, :] = (5, 15, 25)
        image[2:4, 2:4] = (100, 110, 120)
        negative = np.zeros((8, 8, 3), dtype=np.uint8)
        negative[:, :] = (200, 10, 30)
        label_text = "0 0.333333 0.333333 0.666667 0.333333 0.666667 0.666667 0.333333 0.666667\n"
        mask = build_parcel_mask(label_text.splitlines(), image.shape[:2])

        augmented = apply_background_strategy(image, mask, "background_crop", np.random.default_rng(2), [negative])

        self.assertTrue(np.array_equal(augmented[mask], image[mask]))
        self.assertTrue(np.all(augmented[~mask] == np.array([200, 10, 30], dtype=np.uint8)))
        src = self.root / "src.txt"
        dst = self.root / "dst.txt"
        src.write_text(label_text, encoding="utf-8")
        copy_label_unchanged(src, dst)
        self.assertEqual(dst.read_text(encoding="utf-8"), label_text)

    def test_background_crop_skips_negative_images_that_are_too_small(self) -> None:
        source = self.root / "source"
        output = self.root / "output"
        image_dir = source / "images" / "train"
        label_dir = source / "labels" / "train"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)

        save_png(image_dir / "positive.png", np.full((6, 6, 3), 20, dtype=np.uint8))
        (label_dir / "positive.txt").write_text(
            "0 0.333333 0.333333 0.666667 0.333333 0.666667 0.666667 0.333333 0.666667\n",
            encoding="utf-8",
        )
        save_png(image_dir / "a_small_negative.png", np.full((4, 4, 3), 100, dtype=np.uint8))
        (label_dir / "a_small_negative.txt").write_text("", encoding="utf-8")
        save_png(image_dir / "z_large_negative.png", np.full((8, 8, 3), 150, dtype=np.uint8))
        (label_dir / "z_large_negative.txt").write_text("", encoding="utf-8")

        report = augment_split(source, output, "train", 1, ("background_crop",))

        self.assertEqual(report["augmented_images"], 1)
        self.assertTrue((output / "images" / "train" / "positive_bg_background_crop.png").exists())


if __name__ == "__main__":
    unittest.main()
