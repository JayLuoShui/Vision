"""Script to export a trained YOLOv8 model to OpenVINO IR format.

Usage:
    python scripts/export_to_openvino.py --weights best.pt --imgsz 1024

This script uses the Ultralytics export function which handles:
- Conversion to IR (.xml + .bin)
- Optimization for CPU inference
- Input shape specification
- Half-precision (FP16) support if available
"""

from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger


def main() -> None:
    """Export trained YOLO model to OpenVINO format."""
    args = parse_args()
    setup_logging(args.log_level)

    # Load model
    logger.info("Loading model from: {}", args.weights)
    try:
        from ultralytics import YOLO
        model = YOLO(args.weights)
    except ImportError:
        logger.error("ultralytics not installed; cannot export model")
        return
    except Exception as e:
        logger.error("Failed to load model: {}", e)
        return

    # Export to OpenVINO
    logger.info("Exporting to OpenVINO format...")
    logger.info("  Image size: {}", args.imgsz)
    logger.info("  Half precision: {}", args.half)
    logger.info("  Dynamic shapes: {}", args.dynamic)

    try:
        export_results = model.export(
            format='openvino',
            imgsz=args.imgsz,
            half=args.half,
            dynamic=args.dynamic,
            simplify=True,
            int8=False,  # INT8 quantization not needed for V1
            workspace=4,  # GB for optimization
        )

        logger.info("Export complete!")
        logger.info("  Output directory: {}", export_results)

        # Verify output
        output_dir = Path(export_results)
        xml_file = output_dir / "best.xml" if args.weights.endswith('.pt') else output_dir / "openvino_model.xml"
        
        if xml_file.exists():
            logger.info("  Model file: {}", xml_file)
            logger.info("  Model size: {} MB", xml_file.stat().st_size / 1e6)
            
            bin_file = output_dir / "best.bin" if args.weights.endswith('.pt') else output_dir / "openvino_model.bin"
            if bin_file.exists():
                logger.info("  Bin file: {}", bin_file)
                logger.info("  Bin size: {} MB", bin_file.stat().st_size / 1e6)
        else:
            logger.warning("Exported directory: {}", export_results)

    except Exception as e:
        logger.error("Export failed: {}", e)
        return


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Export YOLO model to OpenVINO format"
    )
    parser.add_argument(
        "--weights", type=str, required=True,
        help="Path to trained YOLO model (.pt file)",
    )
    parser.add_argument(
        "--imgsz", type=int, default=1024,
        help="Image size for inference",
    )
    parser.add_argument(
        "--half", action="store_true",
        help="Use FP16 precision",
    )
    parser.add_argument(
        "--dynamic", action="store_true",
        help="Use dynamic input shapes",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    return parser.parse_args()


def setup_logging(level: str = "INFO") -> None:
    """Configure Loguru logging.

    Args:
        level: Log level string.
    """
    from loguru import logger
    import sys
    logger.remove()
    logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", level=level)


if __name__ == "__main__":
    main()
