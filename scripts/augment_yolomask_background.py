import argparse
import json
import random
import shutil
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import yaml


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ("train", "val", "test")
STRATEGIES = ("gaussian_blur", "grayscale", "brightness_contrast", "noise", "background_crop")


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"image read failed: {path}")
    return image


def save_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"image write failed: {path}")
    data.tofile(str(path))


def copy_label_unchanged(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def parse_segment_points(line: str, path: Path | None, line_number: int) -> np.ndarray:
    parts = line.split()
    if len(parts) < 7 or (len(parts) - 1) % 2 != 0:
        where = f"{path}:{line_number}" if path is not None else f"line {line_number}"
        raise RuntimeError(f"invalid YOLO segment line: {where}")
    try:
        cls = int(float(parts[0]))
        values = np.array([float(value) for value in parts[1:]], dtype=np.float32)
    except ValueError as exc:
        where = f"{path}:{line_number}" if path is not None else f"line {line_number}"
        raise RuntimeError(f"invalid number in label: {where}") from exc
    if cls < 0 or np.any(values < 0.0) or np.any(values > 1.0):
        where = f"{path}:{line_number}" if path is not None else f"line {line_number}"
        raise RuntimeError(f"invalid segment value: {where}")
    return values.reshape(-1, 2)


def read_label_lines(path: Path) -> list[str]:
    if not path.exists():
        raise RuntimeError(f"missing label: {path}")
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_parcel_mask(label_lines: list[str], image_size: tuple[int, int]) -> np.ndarray:
    height, width = image_size
    mask = np.zeros((height, width), dtype=np.uint8)
    for line_number, line in enumerate(label_lines, 1):
        points = parse_segment_points(line, None, line_number)
        pixel_points = np.empty_like(points, dtype=np.int32)
        pixel_points[:, 0] = np.rint(points[:, 0] * (width - 1)).astype(np.int32)
        pixel_points[:, 1] = np.rint(points[:, 1] * (height - 1)).astype(np.int32)
        pixel_points[:, 0] = np.clip(pixel_points[:, 0], 0, width - 1)
        pixel_points[:, 1] = np.clip(pixel_points[:, 1], 0, height - 1)
        cv2.fillPoly(mask, [pixel_points], 1)
    return mask.astype(bool)


def has_parcel_mask(label_path: Path) -> bool:
    return bool(read_label_lines(label_path))


def apply_background_strategy(
    image: np.ndarray,
    parcel_mask: np.ndarray,
    strategy: str,
    rng: np.random.Generator,
    negative_images: list[np.ndarray],
) -> np.ndarray:
    if strategy == "gaussian_blur":
        background = cv2.GaussianBlur(image, (31, 31), 0)
    elif strategy == "grayscale":
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        background = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    elif strategy == "brightness_contrast":
        alpha = float(rng.uniform(0.65, 1.35))
        beta = float(rng.uniform(-35.0, 35.0))
        background = np.clip(image.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)
    elif strategy == "noise":
        noise = rng.normal(0.0, 18.0, image.shape).astype(np.float32)
        background = np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    elif strategy == "background_crop":
        if not negative_images:
            raise RuntimeError("background_crop needs at least one negative image")
        negative = negative_images[int(rng.integers(0, len(negative_images)))]
        image_h, image_w = image.shape[:2]
        negative_h, negative_w = negative.shape[:2]
        if negative_h < image_h or negative_w < image_w:
            raise RuntimeError("negative image is smaller than target image")
        max_y = negative_h - image_h
        max_x = negative_w - image_w
        y = int(rng.integers(0, max_y + 1))
        x = int(rng.integers(0, max_x + 1))
        background = negative[y : y + image_h, x : x + image_w].copy()
    else:
        raise RuntimeError(f"unknown background strategy: {strategy}")

    output = background.copy()
    output[parcel_mask] = image[parcel_mask]
    return output


def read_names_and_task(source_root: Path) -> tuple[list[str], str]:
    data_yaml = source_root / "data.yaml"
    if not data_yaml.exists():
        return ["parcel"], "segment"
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    names = data.get("names", {0: "parcel"})
    if isinstance(names, dict):
        name_list = [str(names[idx]) for idx in sorted(names)]
    else:
        name_list = [str(name) for name in names]
    return name_list or ["parcel"], str(data.get("task", "segment"))


def write_data_yaml(output_root: Path, names: list[str], task: str) -> None:
    names_dict = {idx: name for idx, name in enumerate(names)}
    data = {
        "path": output_root.resolve().as_posix(),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "task": task,
        "names": names_dict,
    }
    (output_root / "data.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def iter_images(image_dir: Path) -> list[Path]:
    if not image_dir.exists():
        raise RuntimeError(f"missing image directory: {image_dir}")
    return sorted([path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES], key=lambda path: path.name)


def collect_negative_labels(source_root: Path, split: str) -> list[Path]:
    negative_images: list[Path] = []
    for image_path in iter_images(source_root / "images" / split):
        label_path = source_root / "labels" / split / f"{image_path.stem}.txt"
        if not label_path.exists():
            raise RuntimeError(f"missing label: {label_path}")
        if not read_label_lines(label_path):
            negative_images.append(image_path)
    return negative_images


def choose_negative_crop_image(negative_paths: list[Path], image_size: tuple[int, int], rng: random.Random) -> np.ndarray:
    target_h, target_w = image_size
    candidates = list(negative_paths)
    rng.shuffle(candidates)
    for candidate in candidates:
        negative = load_image(candidate)
        negative_h, negative_w = negative.shape[:2]
        if negative_h >= target_h and negative_w >= target_w:
            return negative
    raise RuntimeError("no negative image is large enough for background_crop")


def copy_original_dataset(source_root: Path, output_root: Path) -> int:
    copied = 0
    for split in SPLITS:
        for image_path in iter_images(source_root / "images" / split):
            label_path = source_root / "labels" / split / f"{image_path.stem}.txt"
            if not label_path.exists():
                raise RuntimeError(f"missing label: {label_path}")
            image_dst = output_root / "images" / split / image_path.name
            label_dst = output_root / "labels" / split / label_path.name
            image_dst.parent.mkdir(parents=True, exist_ok=True)
            label_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image_path, image_dst)
            copy_label_unchanged(label_path, label_dst)
            copied += 1
    return copied


def augment_split(source_root: Path, output_root: Path, split: str, seed: int, strategies: tuple[str, ...]) -> dict[str, int | dict[str, int]]:
    negative_paths = collect_negative_labels(source_root, split)
    if "background_crop" in strategies and not negative_paths:
        raise RuntimeError(f"split has no negative sample for background_crop: {split}")

    python_rng = random.Random(seed)
    strategy_counts: Counter[str] = Counter()
    positive_images = 0
    augmented_images = 0

    for image_path in iter_images(source_root / "images" / split):
        label_path = source_root / "labels" / split / f"{image_path.stem}.txt"
        label_lines = read_label_lines(label_path)
        if not label_lines:
            continue
        positive_images += 1
        strategy = python_rng.choice(strategies)
        rng = np.random.default_rng(python_rng.randrange(0, 2**32))
        image = load_image(image_path)
        parcel_mask = build_parcel_mask(label_lines, image.shape[:2])
        negative_images = []
        if strategy == "background_crop":
            negative_images = [choose_negative_crop_image(negative_paths, image.shape[:2], python_rng)]
        augmented = apply_background_strategy(image, parcel_mask, strategy, rng, negative_images)
        if not np.array_equal(augmented[parcel_mask], image[parcel_mask]):
            raise RuntimeError(f"parcel pixels changed: {image_path}")
        out_stem = f"{image_path.stem}_bg_{strategy}"
        save_png(output_root / "images" / split / f"{out_stem}.png", augmented)
        copy_label_unchanged(label_path, output_root / "labels" / split / f"{out_stem}.txt")
        strategy_counts[strategy] += 1
        augmented_images += 1

    return {
        "positive_images": positive_images,
        "negative_background_images": len(negative_paths),
        "augmented_images": augmented_images,
        "strategy_counts": dict(sorted(strategy_counts.items())),
    }


def augment_dataset(source_root: Path, output_root: Path, splits: tuple[str, ...], seed: int, strategies: tuple[str, ...]) -> dict[str, object]:
    if output_root.exists():
        raise RuntimeError(f"output already exists: {output_root}")
    for strategy in strategies:
        if strategy not in STRATEGIES:
            raise RuntimeError(f"unknown strategy: {strategy}")

    copied_images = copy_original_dataset(source_root, output_root)
    names, task = read_names_and_task(source_root)
    write_data_yaml(output_root, names, task)

    split_reports = {}
    for index, split in enumerate(splits):
        if split not in SPLITS:
            raise RuntimeError(f"unknown split: {split}")
        split_reports[split] = augment_split(source_root, output_root, split, seed + index, strategies)

    augmented_images = sum(int(report["augmented_images"]) for report in split_reports.values())
    report: dict[str, object] = {
        "source": source_root.resolve().as_posix(),
        "output": output_root.resolve().as_posix(),
        "seed": seed,
        "splits_augmented": list(splits),
        "strategies": list(strategies),
        "copied_original_images": copied_images,
        "augmented_images": augmented_images,
        "total_output_images": copied_images + augmented_images,
        "label_policy": "segmentation labels are copied unchanged",
        "parcel_pixel_policy": "augmented images are PNG so parcel pixels stay lossless after saving",
        "split_reports": split_reports,
    }
    (output_root / "dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("datasets/cvds_20260512_yolomask"))
    parser.add_argument("--output", type=Path, default=Path("datasets/cvds_20260512_yolomask_bg_aug"))
    parser.add_argument("--seed", type=int, default=20260513)
    parser.add_argument("--splits", nargs="+", default=["train"], choices=SPLITS)
    parser.add_argument("--strategies", nargs="+", default=list(STRATEGIES), choices=STRATEGIES)
    args = parser.parse_args()

    report = augment_dataset(
        source_root=args.source.resolve(),
        output_root=args.output.resolve(),
        splits=tuple(args.splits),
        seed=args.seed,
        strategies=tuple(args.strategies),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
