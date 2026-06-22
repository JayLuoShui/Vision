"""Standalone demo: run one image through the counting pipeline.

This script exercises the full pipeline from image loading to final
counting. It can be used for quick smoke tests or benchmarking.

Usage:
    python scripts/demo.py --image test_image.jpg
    python scripts/demo.py --image test_image.jpg --count-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Config  # noqa: E402
from app.vision.runner import VisionRunner  # noqa: E402


def main() -> int:
    """Run the demo pipeline."""
    args = parse_args()
    setup_logging(args.log_level)

    config = Config.from_yaml(args.config)

    image_path = Path(args.image)
    if not image_path.exists():
        logger.error("Test image not found: {}", image_path)
        return 1

    image_bytes = image_path.read_bytes()

    logger.info("Loaded test image: {} ({} bytes)", image_path.name, len(image_bytes))

    runner = VisionRunner(config)
    try:
        result = runner.count_from_buffer(
            image_bytes,
            task_id=image_path.stem,
            image_encoding=image_path.suffix.lower().lstrip(".") or "encoded",
        )
        if result.code != 0:
            logger.error("Demo failed: [{}] {}", result.code, result.message)
            return 1

        logger.info("=" * 60)
        logger.info(
            "Result: {} parcel(s) detected in {}ms",
            result.parcel_count,
            result.processing_time_ms,
        )
        logger.info("=" * 60)

        if not args.count_only:
            img_cv2 = cv2.imdecode(
                np.frombuffer(image_bytes, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if img_cv2 is None:
                logger.error("Failed to decode image for display: {}", image_path)
                return 1

            for i, obj in enumerate(result.objects, 1):
                x1, y1, x2, y2 = [int(c) for c in obj.box[:4]]
                cv2.rectangle(img_cv2, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{obj.class_name}: {obj.score:.2f} #{i}"
                cv2.putText(
                    img_cv2,
                    label,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

            cv2.imshow(f"DWS Demo - Count: {result.parcel_count}", img_cv2)
            logger.info("Press any key to close the window...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        return 0
    finally:
        runner.close()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="DWS Vision Count Demo"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to config YAML file",
    )
    parser.add_argument(
        "--image",
        type=str,
        required=True,
        help="Path to test image",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Only print count, don't display image",
    )
    return parser.parse_args()


def setup_logging(level: str = "INFO") -> None:
    """Configure Loguru logging.

    Args:
        level: Log level string.
    """
    logger.remove()
    logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", level=level)


if __name__ == "__main__":
    raise SystemExit(main())
