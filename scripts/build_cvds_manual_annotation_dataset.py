import argparse
import json
import random
import re
import shutil
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import yaml


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class Sample:
    image: Path
    label: Path
    boxes: tuple[tuple[int, float, float, float, float], ...]


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"image read failed: {path}")
    return image


def save_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".jpg", image)
    if not ok:
        raise RuntimeError(f"image write failed: {path}")
    data.tofile(str(path))


def parse_label(path: Path) -> tuple[list[tuple[int, float, float, float, float]], int]:
    boxes: list[tuple[int, float, float, float, float]] = []
    invalid = 0
    if not path.exists():
        return boxes, invalid
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if not parts:
            continue
        ok = False
        if len(parts) == 5:
            try:
                cls = int(float(parts[0]))
                x, y, w, h = [float(v) for v in parts[1:]]
                ok = cls >= 0 and all(0.0 <= v <= 1.0 for v in (x, y, w, h)) and w > 0.0 and h > 0.0
            except ValueError:
                ok = False
        if ok:
            boxes.append((cls, x, y, w, h))
        else:
            invalid += 1
    return boxes, invalid


def write_label(path: Path, boxes: list[tuple[int, float, float, float, float]] | tuple[tuple[int, float, float, float, float], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{cls} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for cls, x, y, w, h in boxes]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_names(source_root: Path) -> list[str]:
    data_yaml = source_root / "data.yaml"
    if not data_yaml.exists():
        return ["parcel"]
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    names = data.get("names", {0: "parcel"})
    if isinstance(names, dict):
        return [str(names[idx]) for idx in sorted(names)]
    return [str(name) for name in names]


def group_key(path: Path) -> str:
    stem = path.stem
    return re.sub(r"_[0-9]{5,}$", "", stem)


def split_samples(samples: list[Sample], train_ratio: float, val_ratio: float, seed: int) -> dict[str, list[Sample]]:
    rng = random.Random(seed)
    groups: dict[str, list[Sample]] = {}
    for sample in samples:
        groups.setdefault(group_key(sample.image), []).append(sample)
    if len(groups) >= 3:
        group_items = list(groups.items())
        rng.shuffle(group_items)
        total = len(samples)
        target_train = int(total * train_ratio)
        target_val = int(total * val_ratio)
        splits = {"train": [], "val": [], "test": []}
        for _, group_samples in group_items:
            if len(splits["train"]) < target_train:
                target = "train"
            elif len(splits["val"]) < target_val:
                target = "val"
            else:
                target = "test"
            splits[target].extend(group_samples)
        return splits

    shuffled = list(samples)
    rng.shuffle(shuffled)
    total = len(shuffled)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)
    return {
        "train": shuffled[:train_end],
        "val": shuffled[train_end:val_end],
        "test": shuffled[val_end:],
    }


def apply_lowlight(image: np.ndarray) -> np.ndarray:
    out = image.astype(np.float32) * 0.55
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_shadow_glare(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    out = image.astype(np.float32)
    shadow = np.zeros((h, w), dtype=np.float32)
    cv2.rectangle(shadow, (0, int(h * 0.15)), (w, int(h * 0.72)), 0.38, -1)
    out *= 1.0 - shadow[..., None]
    cx, cy = int(w * 0.72), int(h * 0.24)
    radius = max(24, int(min(w, h) * 0.16))
    mask = np.zeros((h, w), dtype=np.float32)
    cv2.circle(mask, (cx, cy), radius, 0.42, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), radius / 3)
    out += 255.0 * mask[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_motion_noise(image: np.ndarray, seed: int) -> np.ndarray:
    kernel = np.zeros((7, 7), dtype=np.float32)
    kernel[3, :] = 1.0 / 7.0
    out = cv2.filter2D(image, -1, kernel)
    noise = np.random.default_rng(seed).normal(0, 7, image.shape).astype(np.float32)
    return np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def apply_bright_contrast(image: np.ndarray) -> np.ndarray:
    out = image.astype(np.float32) * 1.18 + 18
    return np.clip(out, 0, 255).astype(np.uint8)


def flip_boxes(boxes: tuple[tuple[int, float, float, float, float], ...]) -> list[tuple[int, float, float, float, float]]:
    return [(cls, 1.0 - x, y, w, h) for cls, x, y, w, h in boxes]


def copy_original(sample: Sample, split: str, output_root: Path) -> None:
    dst_img = output_root / "images" / split / f"{sample.image.stem}.jpg"
    dst_lab = output_root / "labels" / split / f"{sample.image.stem}.txt"
    shutil.copy2(sample.image, dst_img)
    write_label(dst_lab, sample.boxes)


def write_augmented(sample: Sample, output_root: Path) -> int:
    image = load_image(sample.image)
    noise_seed = zlib.crc32(sample.image.stem.encode("utf-8")) & 0xFFFFFFFF
    variants = [
        ("lowlight", apply_lowlight(image), list(sample.boxes)),
        ("shadow_glare", apply_shadow_glare(image), list(sample.boxes)),
        ("motion_noise", apply_motion_noise(image, noise_seed), list(sample.boxes)),
        ("bright_hflip", cv2.flip(apply_bright_contrast(image), 1), flip_boxes(sample.boxes)),
    ]
    for suffix, aug_image, aug_boxes in variants:
        stem = f"{sample.image.stem}_{suffix}"
        save_image(output_root / "images" / "train" / f"{stem}.jpg", aug_image)
        write_label(output_root / "labels" / "train" / f"{stem}.txt", aug_boxes)
    return len(variants)


def draw_preview(sample: Sample, out_path: Path) -> None:
    image = load_image(sample.image)
    h, w = image.shape[:2]
    for cls, x, y, bw, bh in sample.boxes:
        x1 = int((x - bw / 2) * w)
        y1 = int((y - bh / 2) * h)
        x2 = int((x + bw / 2) * w)
        y2 = int((y + bh / 2) * h)
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 229, 255), 2)
        cv2.putText(image, str(cls), (x1, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 229, 255), 2)
    save_image(out_path, image)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("datasets/cvds_annotation_yolo"))
    parser.add_argument("--output", type=Path, default=Path("datasets/cvds_annotation_yolo_labeled_20260508"))
    parser.add_argument("--seed", type=int, default=20260508)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    args = parser.parse_args()

    source_root = args.source.resolve()
    output_root = args.output.resolve()
    if output_root.exists():
        raise RuntimeError(f"output already exists: {output_root}")

    image_dir = source_root / "images" / "train"
    label_dir = source_root / "labels" / "train"
    if not image_dir.exists() or not label_dir.exists():
        raise RuntimeError("source images/train or labels/train does not exist")

    names = read_names(source_root)
    image_paths = sorted([path for path in image_dir.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES])
    samples_to_move: list[tuple[Path, Path, tuple[tuple[int, float, float, float, float], ...]]] = []
    empty_label_images = 0
    missing_label_images = 0
    invalid_lines = 0
    class_counts: Counter[int] = Counter()

    for image_path in image_paths:
        label_path = label_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            missing_label_images += 1
            continue
        boxes, invalid = parse_label(label_path)
        invalid_lines += invalid
        if not boxes:
            empty_label_images += 1
            continue
        for cls, *_ in boxes:
            class_counts[cls] += 1
        samples_to_move.append((image_path, label_path, tuple(boxes)))

    source_images = output_root / "source_annotated" / "images"
    source_labels = output_root / "source_annotated" / "labels"
    source_images.mkdir(parents=True, exist_ok=False)
    source_labels.mkdir(parents=True, exist_ok=False)

    moved_samples: list[Sample] = []
    for image_path, label_path, boxes in samples_to_move:
        dst_img = source_images / f"{image_path.stem}.jpg"
        dst_lab = source_labels / f"{image_path.stem}.txt"
        if dst_img.exists() or dst_lab.exists():
            raise RuntimeError(f"duplicate destination stem: {image_path.stem}")
        shutil.move(str(image_path), str(dst_img))
        shutil.move(str(label_path), str(dst_lab))
        write_label(dst_lab, boxes)
        moved_samples.append(Sample(dst_img, dst_lab, boxes))

    splits = split_samples(moved_samples, args.train_ratio, args.val_ratio, args.seed)
    for split_name, split_samples_list in splits.items():
        (output_root / "images" / split_name).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split_name).mkdir(parents=True, exist_ok=True)
        for sample in split_samples_list:
            copy_original(sample, split_name, output_root)

    augmented_count = 0
    for sample in splits["train"]:
        augmented_count += write_augmented(sample, output_root)

    data = {
        "path": str(output_root).replace("\\", "/"),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {idx: name for idx, name in enumerate(names)},
    }
    (output_root / "data.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    preview_dir = output_root / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for idx, sample in enumerate(moved_samples[:24], 1):
        draw_preview(sample, preview_dir / f"preview_{idx:03d}_{sample.image.name}")

    split_counts = {name: len(items) for name, items in splits.items()}
    final_image_counts = {
        name: len(list((output_root / "images" / name).glob("*.jpg")))
        for name in ("train", "val", "test")
    }
    report = {
        "source_root": str(source_root),
        "output_root": str(output_root),
        "source_total_images": len(image_paths),
        "annotated_images_moved": len(moved_samples),
        "empty_label_images_left_in_source": empty_label_images,
        "missing_label_images": missing_label_images,
        "invalid_label_lines": invalid_lines,
        "boxes_total": sum(class_counts.values()),
        "class_counts": {str(cls): count for cls, count in sorted(class_counts.items())},
        "split_original_counts": split_counts,
        "train_augmented_images": augmented_count,
        "final_image_counts": final_image_counts,
        "augmentation_types": ["lowlight", "shadow_glare", "motion_noise", "bright_hflip"],
        "seed": args.seed,
    }
    (output_root / "dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
