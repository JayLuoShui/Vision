import csv
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import training_monitor  # noqa: E402
from scripts.training_monitor import find_latest_training_run, find_training_process, read_training_snapshot  # noqa: E402


class TrainingMonitorTests(unittest.TestCase):
    def test_finds_training_process_without_shell_command(self) -> None:
        run_dir = Path("runs/package_train/demo")
        fake_processes = [
            {
                "pid": 1234,
                "cmdline": [
                    "python.exe",
                    "scripts/train_yolo26s_manual_annotation.py",
                    "--name",
                    "demo",
                ],
            }
        ]

        with patch.object(training_monitor, "_iter_processes", return_value=fake_processes):
            with patch("subprocess.run", side_effect=AssertionError("不应启动命令行")):
                status = find_training_process(run_dir)

        self.assertTrue(status.running)
        self.assertEqual(status.process_id, 1234)
        self.assertIn("train_yolo26s_manual_annotation.py", status.command_line)

    def test_finds_latest_training_run_with_results_or_args(self) -> None:
        root = Path(self._testMethodName)
        older = root / "runs" / "package_train" / "older"
        newer = root / "runs" / "package_train" / "newer"
        older.mkdir(parents=True)
        newer.mkdir(parents=True)
        (older / "args.yaml").write_text("epochs: 1", encoding="utf-8")
        (newer / "results.csv").write_text("epoch,time\n0,1\n", encoding="utf-8")

        try:
            found = find_latest_training_run(root / "runs" / "package_train")
        finally:
            for file in sorted(root.rglob("*"), reverse=True):
                if file.is_file():
                    file.unlink()
                elif file.is_dir():
                    file.rmdir()
            root.rmdir()

        self.assertEqual(found, newer)

    def test_reads_progress_metrics_args_and_weights(self) -> None:
        root = Path(self._testMethodName)
        run_dir = root / "runs" / "package_train" / "demo"
        weights_dir = run_dir / "weights"
        weights_dir.mkdir(parents=True)
        (run_dir / "args.yaml").write_text(
            "\n".join(
                [
                    "epochs: 60",
                    "imgsz: 832",
                    "batch: 4",
                    "device: '0'",
                    "model: D:\\Demo\\Vision\\weights\\pretrained\\yolo26s.pt",
                    "data: D:\\Demo\\Vision\\datasets\\demo\\data.yaml",
                ]
            ),
            encoding="utf-8",
        )
        with (run_dir / "results.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "epoch",
                    "time",
                    "metrics/precision(B)",
                    "metrics/recall(B)",
                    "metrics/mAP50(B)",
                    "metrics/mAP50-95(B)",
                    "train/box_loss",
                ]
            )
            writer.writerow([0, 10.0, 0.5, 0.4, 0.45, 0.2, 2.0])
            writer.writerow([12, 3410.79, 0.85764, 0.87377, 0.84749, 0.42052, 1.00172])
        (weights_dir / "best.pt").write_bytes(b"best")
        (weights_dir / "last.pt").write_bytes(b"last")

        try:
            snapshot = read_training_snapshot(run_dir)
        finally:
            for file in sorted(root.rglob("*"), reverse=True):
                if file.is_file():
                    file.unlink()
                elif file.is_dir():
                    file.rmdir()
            root.rmdir()

        self.assertEqual(snapshot.run_dir, run_dir)
        self.assertEqual(snapshot.total_epochs, 60)
        self.assertEqual(snapshot.finished_epochs, 13)
        self.assertAlmostEqual(snapshot.progress_percent, 21.67, places=2)
        self.assertAlmostEqual(snapshot.latest_metrics["metrics/mAP50(B)"], 0.84749)
        self.assertAlmostEqual(snapshot.best_map50, 0.84749)
        self.assertAlmostEqual(snapshot.best_map5095, 0.42052)
        self.assertEqual(snapshot.args["imgsz"], "832")
        self.assertTrue(snapshot.weights["last.pt"].exists)


if __name__ == "__main__":
    unittest.main()
