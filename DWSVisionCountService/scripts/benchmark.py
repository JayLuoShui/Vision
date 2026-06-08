from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Config  # noqa: E402
from app.schemas import ImageMeta  # noqa: E402
from app.vision.counter import ParcelCounter  # noqa: E402


def percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * ratio)))
    return ordered[index]


def benchmark_image(counter: ParcelCounter, path: Path) -> dict:
    image_bytes = path.read_bytes()
    meta = ImageMeta(
        task_id=path.stem,
        image_encoding=path.suffix.lower().lstrip("."),
        image_len=len(image_bytes),
    )
    return counter.count_bytes(meta, image_bytes).to_dict() | {"file": path.name}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image_dir", required=True)
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--save_csv", default=None)
    args = parser.parse_args()

    config = Config.from_yaml(args.config)
    counter = ParcelCounter(config)
    counter.load()
    rows = []
    for path in sorted(Path(args.image_dir).glob("*")):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
            continue
        row = benchmark_image(counter, path)
        rows.append(row)
        print(
            f"{path.name}: count={row['parcel_count']} "
            f"time={row['processing_time_ms']}ms code={row['code']}"
        )

    times = [row["processing_time_ms"] for row in rows]
    infer_times = [row["inference_time_ms"] for row in rows]
    print({
        "total_images": len(rows),
        "avg_processing_time_ms": int(sum(times) / len(times)) if times else 0,
        "p50_processing_time_ms": percentile(times, 0.50),
        "p95_processing_time_ms": percentile(times, 0.95),
        "avg_inference_time_ms": int(sum(infer_times) / len(infer_times)) if infer_times else 0,
        "avg_decode_time_ms": int(sum(row["decode_time_ms"] for row in rows) / len(rows)) if rows else 0,
        "error_count": sum(1 for row in rows if row["code"] != 0),
    })
    if args.save_csv and rows:
        with open(args.save_csv, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    return 1 if not rows or any(row["code"] != 0 for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
