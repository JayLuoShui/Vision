from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Config  # noqa: E402
from app.schemas import ImageMeta  # noqa: E402
from app.utils.image_io import decode_image_bytes_with_info  # noqa: E402


def _scale_point(
    point: tuple[int, int],
    scale_x: float,
    scale_y: float,
) -> tuple[int, int]:
    return int(round(point[0] * scale_x)), int(round(point[1] * scale_y))


def draw_calibration_overlay(image_path: Path, config: Config, reduce_factor: int) -> np.ndarray:
    image_bytes = image_path.read_bytes()
    meta = ImageMeta(
        task_id=image_path.stem,
        image_encoding=image_path.suffix.lower().lstrip("."),
        image_len=len(image_bytes),
    )
    decoded = decode_image_bytes_with_info(meta, image_bytes, reduce_factor=reduce_factor)
    image = decoded.image_bgr.copy()
    scale_x = decoded.decode_scale_x
    scale_y = decoded.decode_scale_y

    x1, y1, x2, y2 = config.get_roi_rect()
    cv2.rectangle(
        image,
        _scale_point((x1, y1), scale_x, scale_y),
        _scale_point((x2, y2), scale_x, scale_y),
        (0, 255, 0),
        3,
    )
    polygon = np.array(
        [
            _scale_point((int(x), int(y)), scale_x, scale_y)
            for x, y in config.belt_polygon
        ],
        dtype=np.int32,
    ).reshape((-1, 1, 2))
    cv2.polylines(image, [polygon], isClosed=True, color=(255, 255, 0), thickness=3)
    for region in config.ignore_regions:
        cv2.rectangle(
            image,
            _scale_point((region.x1, region.y1), scale_x, scale_y),
            _scale_point((region.x2, region.y2), scale_x, scale_y),
            (0, 0, 255),
            3,
        )
        cv2.putText(
            image,
            region.name or "ignore",
            _scale_point((region.x1, max(0, region.y1 - 10)), scale_x, scale_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    cv2.putText(
        image,
        "green=ROI cyan=belt red=ignore",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="DWS ROI 标定预览工具")
    parser.add_argument("--image", required=True, help="现场图片路径")
    parser.add_argument("--config", default="config/config.yaml", help="配置文件路径")
    parser.add_argument("--output", default="debug/roi_calibration_preview.jpg", help="输出预览图路径")
    parser.add_argument("--reduce", type=int, default=1, choices=[1, 2, 4, 8], help="JPEG reduce 预览倍率")
    args = parser.parse_args()

    config = Config.from_yaml(args.config)
    preview = draw_calibration_overlay(Path(args.image), config, args.reduce)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), preview):
        raise RuntimeError(f"failed to write preview image: {output}")
    print(output)


if __name__ == "__main__":
    main()
