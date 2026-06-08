import json
import math
import random
import shutil
import time
from pathlib import Path

import cv2
import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"
SOURCE_ROOT = DATASETS / "sources" / "roboflow_downloads"
OUT = DATASETS / "cvds_package_yolo26"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
RANDOM_SEED = 20260506


SOURCES = [
    {
        "name": "roboflow_packages_project_33xgh",
        "path": SOURCE_ROOT / "search_packages_project_33xgh",
        "url": "https://universe.roboflow.com/project-33xgh/packages-rg6yr/dataset/1",
        "license": "CC BY 4.0",
        "keep_classes": {1},
        "reason": "class 1 is packages; class 0 is not a package label.",
    },
    {
        "name": "roboflow_package_project_33xgh",
        "path": SOURCE_ROOT / "package_project_33xgh",
        "url": "https://universe.roboflow.com/project-33xgh/package-73wdr/dataset/1",
        "license": "CC BY 4.0",
        "keep_classes": {1},
        "reason": "class 1 is box/package; class 0 is not a package label.",
    },
    {
        "name": "roboflow_package_damage",
        "path": SOURCE_ROOT / "package_damage",
        "url": "https://universe.roboflow.com/deteksipaketrusak/package-kglu1/dataset/2",
        "license": "CC BY 4.0",
        "keep_classes": {1},
        "reason": "class 1 is package; class 0 is damaged area and must not be treated as a parcel box.",
    },
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def reset_output() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for rel in ["images/train", "images/val", "images/test", "labels/train", "labels/val", "labels/test", "previews"]:
        ensure_dir(OUT / rel)


def image_for_label(label: Path) -> Path | None:
    image_dir = label.parents[1] / "images"
    for suffix in IMAGE_SUFFIXES:
        candidate = image_dir / f"{label.stem}{suffix}"
        if candidate.exists():
            return candidate
    for candidate in image_dir.glob(label.stem + ".*"):
        if candidate.suffix.lower() in IMAGE_SUFFIXES:
            return candidate
    return None


def read_yolo_label(path: Path, keep_classes: set[int]) -> list[list[float]]:
    boxes: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        cls = int(float(parts[0]))
        if cls not in keep_classes:
            continue
        nums = [float(v) for v in parts[1:]]
        if len(nums) == 4:
            x, y, w, h = nums
        else:
            xs = nums[0::2]
            ys = nums[1::2]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            x, y, w, h = (xmin + xmax) / 2, (ymin + ymax) / 2, xmax - xmin, ymax - ymin
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            continue
        boxes.append([0, x, y, w, h])
    return boxes


def write_label(path: Path, boxes: list[list[float]]) -> None:
    ensure_dir(path.parent)
    deduped = []
    seen = set()
    for box in boxes:
        key = tuple(round(float(v), 6) for v in box)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(box)
    text = "\n".join(f"{int(c)} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for c, x, y, w, h in deduped)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"读取图片失败：{path}")
    return img


def save_image(path: Path, img: np.ndarray) -> None:
    ensure_dir(path.parent)
    ext = path.suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
        ext = ".jpg"
    ok, data = cv2.imencode(ext, img)
    if not ok:
        raise RuntimeError(f"写入图片失败：{path}")
    data.tofile(str(path))


def copy_image(src: Path, dst: Path) -> None:
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def collect_sources() -> tuple[list[dict], dict]:
    items: list[dict] = []
    stats: dict[str, dict] = {}
    split_map = {"train": "train", "valid": "val", "test": "test"}
    for source in SOURCES:
        root = source["path"]
        source_stats = {"images": 0, "boxes": 0, "skipped_empty": 0, "missing_image": 0}
        for src_split, dst_split in split_map.items():
            label_dir = root / src_split / "labels"
            if not label_dir.exists():
                continue
            for label in sorted(label_dir.glob("*.txt")):
                boxes = read_yolo_label(label, source["keep_classes"])
                if not boxes:
                    source_stats["skipped_empty"] += 1
                    continue
                image = image_for_label(label)
                if image is None:
                    source_stats["missing_image"] += 1
                    continue
                stem = f"{source['name']}_{label.stem}"
                dst_img = OUT / "images" / dst_split / f"{stem}{image.suffix.lower()}"
                dst_label = OUT / "labels" / dst_split / f"{stem}.txt"
                copy_image(image, dst_img)
                write_label(dst_label, boxes)
                source_stats["images"] += 1
                source_stats["boxes"] += len(boxes)
                items.append(
                    {
                        "source": source["name"],
                        "split": dst_split,
                        "image": str(dst_img),
                        "label": str(dst_label),
                        "boxes": len(boxes),
                    }
                )
        stats[source["name"]] = source_stats
    return items, stats


def adjust_light(img: np.ndarray, alpha: float, beta: float, gamma: float) -> np.ndarray:
    out = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
    table = np.array([((i / 255.0) ** gamma) * 255 for i in range(256)]).astype("uint8")
    return cv2.LUT(out, table)


def add_shadow(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    mask = np.zeros((h, w), dtype=np.float32)
    pts = np.array(
        [
            [random.randint(0, w // 2), 0],
            [random.randint(w // 2, w), 0],
            [random.randint(w // 2, w), h],
            [random.randint(0, w // 2), h],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(mask, [pts], 0.42)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(12, w // 18))
    out = img.astype(np.float32) * (1.0 - mask[..., None])
    return np.clip(out, 0, 255).astype(np.uint8)


def add_glare(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    layer = np.zeros_like(img, dtype=np.uint8)
    cx = random.randint(w // 6, max(w // 6 + 1, 5 * w // 6))
    cy = random.randint(h // 6, max(h // 6 + 1, 5 * h // 6))
    axes = (random.randint(max(10, w // 16), max(12, w // 4)), random.randint(max(8, h // 24), max(10, h // 8)))
    cv2.ellipse(layer, (cx, cy), axes, random.randint(0, 180), 0, 360, (255, 255, 255), -1)
    layer = cv2.GaussianBlur(layer, (0, 0), sigmaX=max(8, w // 32))
    return cv2.addWeighted(img, 1.0, layer, 0.32, 0)


def add_noise(img: np.ndarray) -> np.ndarray:
    noise = np.random.normal(0, 9, img.shape).astype(np.float32)
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def flip_boxes(boxes: list[list[float]]) -> list[list[float]]:
    return [[c, 1.0 - x, y, w, h] for c, x, y, w, h in boxes]


def read_output_label(path: Path) -> list[list[float]]:
    boxes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 5:
            boxes.append([int(float(parts[0]))] + [float(x) for x in parts[1:]])
    return boxes


def augment_train(items: list[dict]) -> dict:
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    recipes = [
        ("lowlight", lambda img: adjust_light(img, 0.68, -20, 1.25), False),
        ("overlight", lambda img: adjust_light(img, 1.25, 24, 0.82), False),
        ("shadow", add_shadow, False),
        ("glare", add_glare, False),
        ("blur", lambda img: cv2.GaussianBlur(img, (5, 5), 0), False),
        ("noise", add_noise, False),
        ("flip", lambda img: cv2.flip(img, 1), True),
    ]
    stats = {"images": 0, "boxes": 0}
    for item in [x for x in items if x["split"] == "train"]:
        img_path = Path(item["image"])
        label_path = Path(item["label"])
        boxes = read_output_label(label_path)
        if not boxes:
            continue
        img = load_image(img_path)
        for suffix, func, flip in recipes:
            dst_img = img_path.with_name(f"{img_path.stem}_aug_{suffix}{img_path.suffix}")
            dst_label = label_path.with_name(f"{label_path.stem}_aug_{suffix}.txt")
            save_image(dst_img, func(img.copy()))
            new_boxes = flip_boxes(boxes) if flip else boxes
            write_label(dst_label, new_boxes)
            stats["images"] += 1
            stats["boxes"] += len(new_boxes)
    return stats


def validate_dataset() -> dict:
    summary: dict[str, dict] = {}
    for split in ["train", "val", "test"]:
        image_dir = OUT / "images" / split
        label_dir = OUT / "labels" / split
        images = sorted([p for p in image_dir.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES])
        labels = sorted(label_dir.rglob("*.txt"))
        image_stems = {p.stem for p in images}
        label_stems = {p.stem for p in labels}
        bad = []
        boxes = 0
        for label in labels:
            for line in label.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    bad.append(str(label))
                    continue
                c, x, y, w, h = [float(v) for v in parts]
                if c != 0 or not all(math.isfinite(v) for v in [x, y, w, h]) or not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    bad.append(str(label))
                boxes += 1
        summary[split] = {
            "images": len(images),
            "labels": len(labels),
            "boxes": boxes,
            "images_without_labels": len(image_stems - label_stems),
            "labels_without_images": len(label_stems - image_stems),
            "bad_labels": sorted(set(bad))[:20],
        }
    return summary


def draw_previews(limit: int = 12) -> None:
    preview_dir = OUT / "previews"
    ensure_dir(preview_dir)
    labels = list((OUT / "labels" / "train").glob("*.txt"))[:limit]
    for label in labels:
        image = next((OUT / "images" / "train").glob(label.stem + ".*"), None)
        if image is None:
            continue
        img = load_image(image)
        h, w = img.shape[:2]
        for _, x, y, bw, bh in read_output_label(label):
            x1 = int((x - bw / 2) * w)
            y1 = int((y - bh / 2) * h)
            x2 = int((x + bw / 2) * w)
            y2 = int((y + bh / 2) * h)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 220, 0), 2)
            cv2.putText(img, "parcel", (x1, max(16, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 2)
        save_image(preview_dir / f"{label.stem}.jpg", img)


def write_yaml() -> None:
    data = {
        "path": str(OUT).replace("\\", "/"),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {0: "parcel"},
    }
    (OUT / "data.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_source_note(report: dict) -> None:
    lines = [
        "# CVDS 包裹检测数据集",
        "",
        "目标：训练 YOLO26 单类包裹检测模型，类别统一为 `parcel`。",
        "",
        "处理原则：只保留表示包裹整体的标注框，跳过损坏区域、占位类、说明性类别。",
        "",
        "增强：只作用于训练集，包含低光、过曝、阴影、眩光、轻微模糊、噪声、水平翻转；验证集和测试集不增强。",
        "",
        "来源：",
    ]
    for source in SOURCES:
        lines.append(f"- {source['name']}: {source['url']}，许可：{source['license']}，保留规则：{source['reason']}")
    lines.extend(["", "统计：", "```json", json.dumps(report["summary"], ensure_ascii=False, indent=2), "```"])
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    reset_output()
    items, source_stats = collect_sources()
    augmentation_stats = augment_train(items)
    write_yaml()
    draw_previews()
    summary = validate_dataset()
    report = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "output": str(OUT),
        "class_map": {"0": "parcel"},
        "source_stats": source_stats,
        "augmentation": augmentation_stats,
        "summary": summary,
    }
    (OUT / "dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_source_note(report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
