import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.train_yolomask_yolo26seg import choose_training_profile, ensure_source_path  # noqa: E402


class YoloMaskTrainProfileTests(unittest.TestCase):
    def test_rtx_4050_six_gb_uses_yolo26s_seg_profile(self) -> None:
        profile = choose_training_profile(total_vram_mib=6141)

        self.assertEqual(profile.model, "weights/pretrained/yolo26s-seg.pt")
        self.assertEqual(profile.imgsz, 960)
        self.assertEqual(profile.batch, 2)
        self.assertEqual(profile.workers, 2)
        self.assertEqual(profile.optimizer, "AdamW")

    def test_low_vram_is_rejected_instead_of_silent_cpu_fallback(self) -> None:
        with self.assertRaises(RuntimeError):
            choose_training_profile(total_vram_mib=3000)

    def test_source_path_is_inserted_before_site_packages(self) -> None:
        source = ROOT / "ultralytics"
        original = list(sys.path)
        try:
            ensure_source_path(source)
            self.assertEqual(Path(sys.path[0]), source)
        finally:
            sys.path[:] = original


if __name__ == "__main__":
    unittest.main()
