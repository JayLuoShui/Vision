import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class SegObject:
    cls: int
    points: tuple[float, ...]


@dataclass(frozen=True)
class Sample:
    image: Path
    label: Path
    objects: tuple[SegObject, ...]


def parse_seg_label(path: Path) -> tuple[SegObject, ...]:
    objects: list[SegObject] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 7 or (len(parts) - 1) % 2 != 0:
            raise RuntimeError(f"invalid YOLO segment line: {path}:{line_number}")
        try:
            cls = int(float(parts[0]))
            values = tuple(float(value) for value in parts[1:])
        except ValueError as exc:
            raise RuntimeError(f"invalid number in label: {path}:{line_number}") from exc
        if cls < 0:
            raise RuntimeError(f"invalid class id in label: {path}:{line_number}")
        if any(value < 0.0 or value > 1.0 for value in values):
            raise RuntimeError(f"point outside 0..1 in label: {path}:{line_number}")
        xs = values[0::2]
        ys = values[1::2]
        if max(xs) <= min(xs) or max(ys) <= min(ys):
            raise RuntimeError(f"zero-area polygon in label: {path}:{line_number}")
        objects.append(SegObject(cls=cls, points=values))
    return tuple(objects)


def group_key(path: Path) -> str:
    return re.sub(r"_[0-9]{5,}$", "", path.stem)


def stable_hash(text: str) -> int:
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:12], 16)


def split_samples(samples: list[Sample]) -> dict[str, list[Sample]]:
    groups: dict[str, list[Sample]] = {}
    for sample in samples:
        groups.setdefault(group_key(sample.image), []).append(sample)

    group_items = sorted(groups.items(), key=lambda item: stable_hash(item[0]))
    total = len(samples)
    targets = {"train": round(total * 0.8), "val": round(total * 0.1), "test": total}
    targets["test"] = total - targets["train"] - targets["val"]
    splits: dict[str, list[Sample]] = {split: [] for split in SPLITS}
    split_counts = {split: 0 for split in SPLITS}
    priority = {"train": 0, "val": 1, "test": 2}

    for _, group_samples in group_items:
        split = max(
            SPLITS,
            key=lambda name: (
                (targets[name] - split_counts[name]) / max(targets[name], 1),
                -priority[name],
            ),
        )
        splits[split].extend(group_samples)
        split_counts[split] += len(group_samples)

    return splits


def copy_image(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def format_segment(objects: tuple[SegObject, ...]) -> str:
    lines = []
    for obj in objects:
        values = " ".join(f"{value:.6f}" for value in obj.points)
        lines.append(f"{obj.cls} {values}")
    return "\n".join(lines) + ("\n" if lines else "")


def format_detection(objects: tuple[SegObject, ...]) -> str:
    lines = []
    for obj in objects:
        xs = obj.points[0::2]
        ys = obj.points[1::2]
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        width = x2 - x1
        height = y2 - y1
        lines.append(f"{obj.cls} {cx:.6f} {cy:.6f} {width:.6f} {height:.6f}")
    return "\n".join(lines) + ("\n" if lines else "")


def write_data_yaml(path: Path, task: str, names: list[str]) -> None:
    names_text = "\n".join(f"  {idx}: {name}" for idx, name in enumerate(names))
    text = (
        f"path: {path.resolve().as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        f"task: {task}\n"
        "names:\n"
        f"{names_text}\n"
    )
    write_text(path / "data.yaml", text)


def read_names(source_root: Path) -> list[str]:
    data_yaml = source_root / "data.yaml"
    if not data_yaml.exists():
        return ["parcel"]
    names: list[str] = []
    in_names = False
    for line in data_yaml.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "names:":
            in_names = True
            continue
        if in_names:
            if not line.startswith("  "):
                break
            if ":" in stripped:
                _, value = stripped.split(":", 1)
                names.append(value.strip().strip("'\""))
    return names or ["parcel"]


def prepare_output_root(path: Path) -> None:
    if path.exists():
        raise RuntimeError(f"output already exists: {path}")
    for split in SPLITS:
        (path / "images" / split).mkdir(parents=True, exist_ok=False)
        (path / "labels" / split).mkdir(parents=True, exist_ok=False)


def move_remaining_samples(remaining: list[Path], source_root: Path, unannotated_root: Path) -> int:
    if unannotated_root.exists():
        raise RuntimeError(f"unannotated output already exists: {unannotated_root}")
    moved = 0
    image_dir = unannotated_root / "images" / "train"
    label_dir = unannotated_root / "labels" / "train"
    image_dir.mkdir(parents=True, exist_ok=False)
    label_dir.mkdir(parents=True, exist_ok=False)
    for image_path in remaining:
        label_path = source_root / "labels" / "train" / f"{image_path.stem}.txt"
        shutil.move(str(image_path), str(image_dir / image_path.name))
        if label_path.exists():
            shutil.move(str(label_path), str(label_dir / label_path.name))
        moved += 1
    write_data_yaml(unannotated_root, "segment", read_names(source_root))
    return moved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("datasets/cvds_20260512"))
    parser.add_argument("--target-image", default="video_20260512_105934_000350.jpg")
    parser.add_argument("--mask-output", type=Path, default=Path("datasets/cvds_20260512_yolomask"))
    parser.add_argument("--det-output", type=Path, default=Path("datasets/cvds_20260512_yolo26"))
    parser.add_argument("--unannotated-output", type=Path, default=Path("datasets/未标注"))
    args = parser.parse_args()

    source_root = args.source.resolve()
    image_dir = source_root / "images" / "train"
    label_dir = source_root / "labels" / "train"
    if not image_dir.exists() or not label_dir.exists():
        raise RuntimeError("source images/train or labels/train does not exist")

    images = sorted([path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES], key=lambda path: path.name)
    image_names = [path.name for path in images]
    if args.target_image not in image_names:
        raise RuntimeError(f"target image not found: {args.target_image}")
    target_index = image_names.index(args.target_image)
    annotated_images = images[: target_index + 1]
    remaining_images = images[target_index + 1 :]

    samples: list[Sample] = []
    empty_labels = 0
    class_counts: Counter[int] = Counter()
    for image_path in annotated_images:
        label_path = label_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            raise RuntimeError(f"missing label for annotated image: {image_path.name}")
        objects = parse_seg_label(label_path)
        if not objects:
            empty_labels += 1
        for obj in objects:
            class_counts[obj.cls] += 1
        samples.append(Sample(image=image_path, label=label_path, objects=objects))

    mask_output = args.mask_output.resolve()
    det_output = args.det_output.resolve()
    unannotated_output = args.unannotated_output.resolve()
    prepare_output_root(mask_output)
    prepare_output_root(det_output)

    names = read_names(source_root)
    splits = split_samples(samples)
    for split, samples_in_split in splits.items():
        for sample in samples_in_split:
            copy_image(sample.image, mask_output / "images" / split / sample.image.name)
            copy_image(sample.image, det_output / "images" / split / sample.image.name)
            write_text(mask_output / "labels" / split / f"{sample.image.stem}.txt", format_segment(sample.objects))
            write_text(det_output / "labels" / split / f"{sample.image.stem}.txt", format_detection(sample.objects))

    write_data_yaml(mask_output, "segment", names)
    write_data_yaml(det_output, "detect", names)
    moved_unannotated = move_remaining_samples(remaining_images, source_root, unannotated_output)

    report = {
        "source": source_root.as_posix(),
        "target_image": args.target_image,
        "annotated_images": len(annotated_images),
        "empty_label_images": empty_labels,
        "segmentation_objects": sum(class_counts.values()),
        "class_counts": {str(cls): count for cls, count in sorted(class_counts.items())},
        "remaining_images_moved_to_unannotated": moved_unannotated,
        "splits": {split: len(items) for split, items in splits.items()},
        "mask_output": mask_output.as_posix(),
        "det_output": det_output.as_posix(),
        "unannotated_output": unannotated_output.as_posix(),
        "split_strategy": "80/10/10 by source clip group",
    }
    write_text(mask_output / "dataset_report.json", json.dumps(report, ensure_ascii=False, indent=2))
    write_text(det_output / "dataset_report.json", json.dumps(report, ensure_ascii=False, indent=2))
    write_text(unannotated_output / "dataset_report.json", json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
