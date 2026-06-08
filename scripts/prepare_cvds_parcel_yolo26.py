import csv
import json
import math
import random
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import cv2
import numpy as np
import requests
import yaml
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"
SOURCES = DATASETS / "sources"
PACKDET = SOURCES / "packdet_hf"
OPENIMAGES = SOURCES / "openimages_box"
OUT = DATASETS / "cvds_parcel_yolo26"

PACKDET_BASE = "https://huggingface.co/datasets/industoai/PackDet/resolve/main"
OPENIMAGES_BOXES = "https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv"
OPENIMAGES_IMAGES = "https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv"
OPENIMAGES_CLASSES = "https://storage.googleapis.com/openimages/v6/oidv6-class-descriptions.csv"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
OPENIMAGES_LABELS = {
    "/m/025dyy": "Box",
    "/m/033rv2": "Carton",
    "/m/03q7pgh": "Cardboard",
    "/m/05gqfk": "Plastic bag",
}
OPENIMAGES_MAX_IMAGES = 220
RANDOM_SEED = 20260506


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def download_file(url: str, dst: Path, retries: int = 4, timeout: int = 60) -> bool:
    if dst.exists() and dst.stat().st_size > 0:
        return True
    ensure_dir(dst.parent)
    tmp = dst.with_suffix(dst.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}")
                with tmp.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            tmp.replace(dst)
            return True
        except Exception:
            if tmp.exists():
                tmp.unlink()
            if attempt == retries:
                return False
            time.sleep(1.5 * attempt)
    return False


def packdet_url(rel_path: str) -> str:
    return f"{PACKDET_BASE}/{quote(rel_path.replace('\\', '/'))}"


def read_lines(path: Path) -> list[str]:
    return [x.strip().replace("\\", "/") for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def download_packdet() -> dict:
    ensure_dir(PACKDET)
    for rel in ["data/Train.txt", "data/Validation.txt", "data/data.yaml", "README.md", "LICENSE"]:
        download_file(packdet_url(rel), PACKDET / rel)

    tasks: list[tuple[str, Path]] = []
    for split_file in ["data/Train.txt", "data/Validation.txt"]:
        for img_rel in read_lines(PACKDET / split_file):
            label_rel = img_rel.replace("images/", "labels/").rsplit(".", 1)[0] + ".txt"
            tasks.append((img_rel, PACKDET / img_rel))
            tasks.append((label_rel, PACKDET / label_rel))

    ok = 0
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(download_file, packdet_url(rel), dst): rel for rel, dst in tasks}
        for future in as_completed(futures):
            rel = futures[future]
            if future.result():
                ok += 1
            else:
                failed.append(rel)
    return {"source": "industoai/PackDet", "downloaded_or_existing_files": ok, "failed_files": failed}


def download_openimages_metadata() -> None:
    ensure_dir(OPENIMAGES)
    download_file(OPENIMAGES_BOXES, OPENIMAGES / "validation-annotations-bbox.csv")
    download_file(OPENIMAGES_IMAGES, OPENIMAGES / "validation-images-with-rotation.csv")
    download_file(OPENIMAGES_CLASSES, OPENIMAGES / "class-descriptions.csv")


def parse_yolo_or_seg_label(path: Path) -> list[list[float]]:
    boxes: list[list[float]] = []
    if not path.exists():
        return boxes
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        nums = [float(x) for x in parts[1:]]
        if len(nums) == 4:
            x, y, w, h = nums
            xmin, xmax = x - w / 2, x + w / 2
            ymin, ymax = y - h / 2, y + h / 2
        else:
            xs = nums[0::2]
            ys = nums[1::2]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
        xmin, xmax = max(0.0, xmin), min(1.0, xmax)
        ymin, ymax = max(0.0, ymin), min(1.0, ymax)
        w, h = xmax - xmin, ymax - ymin
        if w > 0.001 and h > 0.001:
            boxes.append([0, (xmin + xmax) / 2, (ymin + ymax) / 2, w, h])
    return boxes


def write_label(path: Path, boxes: list[list[float]]) -> None:
    ensure_dir(path.parent)
    lines = [f"{int(cls)} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for cls, x, y, w, h in boxes]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def copy_image(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    ensure_dir(dst.parent)
    if not dst.exists():
        shutil.copy2(src, dst)
    return True


def collect_packdet(out_items: list[dict]) -> dict:
    counts = {"train_images": 0, "val_images": 0, "boxes": 0, "skipped": 0}
    split_map = {"data/Train.txt": "train", "data/Validation.txt": "val"}
    for split_file, out_split in split_map.items():
        for img_rel in read_lines(PACKDET / split_file):
            src_img = PACKDET / img_rel
            label_rel = img_rel.replace("images/", "labels/").rsplit(".", 1)[0] + ".txt"
            src_label = PACKDET / label_rel
            boxes = parse_yolo_or_seg_label(src_label)
            if not boxes:
                counts["skipped"] += 1
                continue
            stem = "packdet_" + src_img.stem
            ext = src_img.suffix.lower()
            dst_img = OUT / "images" / out_split / f"{stem}{ext}"
            dst_label = OUT / "labels" / out_split / f"{stem}.txt"
            if copy_image(src_img, dst_img):
                write_label(dst_label, boxes)
                counts[f"{out_split}_images"] += 1
                counts["boxes"] += len(boxes)
                out_items.append({"source": "PackDet", "split": out_split, "image": str(dst_img), "label": str(dst_label), "boxes": len(boxes)})
    return counts


def collect_openimages(out_items: list[dict]) -> dict:
    download_openimages_metadata()
    image_meta: dict[str, dict] = {}
    with (OPENIMAGES / "validation-images-with-rotation.csv").open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            image_meta[row["ImageID"]] = row

    by_image: dict[str, list[list[float]]] = {}
    with (OPENIMAGES / "validation-annotations-bbox.csv").open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["LabelName"] not in OPENIMAGES_LABELS:
                continue
            if row.get("IsGroupOf") == "1":
                continue
            xmin, xmax = float(row["XMin"]), float(row["XMax"])
            ymin, ymax = float(row["YMin"]), float(row["YMax"])
            w, h = xmax - xmin, ymax - ymin
            if w <= 0.02 or h <= 0.02:
                continue
            by_image.setdefault(row["ImageID"], []).append([0, (xmin + xmax) / 2, (ymin + ymax) / 2, w, h])

    rng = random.Random(RANDOM_SEED)
    image_ids = [x for x in by_image if x in image_meta and image_meta[x].get("Thumbnail300KURL")]
    rng.shuffle(image_ids)
    image_ids = image_ids[:OPENIMAGES_MAX_IMAGES]

    raw_dir = OPENIMAGES / "images"
    counts = {"val_images": 0, "boxes": 0, "failed": 0}
    for image_id in image_ids:
        meta = image_meta[image_id]
        src = raw_dir / f"{image_id}.jpg"
        if not download_file(meta["Thumbnail300KURL"], src):
            counts["failed"] += 1
            continue
        dst_img = OUT / "images" / "val" / f"openimages_{image_id}.jpg"
        dst_label = OUT / "labels" / "val" / f"openimages_{image_id}.txt"
        if copy_image(src, dst_img):
            boxes = by_image[image_id]
            write_label(dst_label, boxes)
            counts["val_images"] += 1
            counts["boxes"] += len(boxes)
            out_items.append({"source": "Open Images", "split": "val", "image": str(dst_img), "label": str(dst_label), "boxes": len(boxes)})
    return counts


def load_image(path: Path) -> np.ndarray:
    arr = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"cannot read image: {path}")
    return img


def save_image(path: Path, img: np.ndarray) -> None:
    ensure_dir(path.parent)
    ext = path.suffix.lower()
    ok, data = cv2.imencode(ext if ext in [".jpg", ".jpeg", ".png"] else ".jpg", img)
    if not ok:
        raise RuntimeError(f"cannot encode image: {path}")
    data.tofile(str(path))


def read_label(path: Path) -> list[list[float]]:
    boxes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) == 5:
            boxes.append([int(float(parts[0]))] + [float(x) for x in parts[1:]])
    return boxes


def adjust_light(img: np.ndarray, alpha: float, beta: float, gamma: float = 1.0) -> np.ndarray:
    out = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
    if abs(gamma - 1.0) > 1e-6:
        table = np.array([((i / 255.0) ** gamma) * 255 for i in range(256)]).astype("uint8")
        out = cv2.LUT(out, table)
    return out


def add_shadow(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    mask = np.zeros((h, w), dtype=np.float32)
    left = random.randint(0, max(1, w // 3))
    right = random.randint(max(left + 1, w // 2), w)
    cv2.rectangle(mask, (left, 0), (right, h), 0.45, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(15, w // 12))
    out = img.astype(np.float32) * (1.0 - mask[..., None])
    return np.clip(out, 0, 255).astype(np.uint8)


def add_glare(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    overlay = img.copy().astype(np.float32)
    cx, cy = random.randint(w // 5, 4 * w // 5), random.randint(h // 5, 4 * h // 5)
    ax, ay = random.randint(max(12, w // 12), max(14, w // 4)), random.randint(max(10, h // 16), max(12, h // 5))
    cv2.ellipse(overlay, (cx, cy), (ax, ay), random.randint(0, 180), 0, 360, (255, 255, 255), -1)
    overlay = cv2.GaussianBlur(overlay, (0, 0), sigmaX=max(8, w // 30))
    out = cv2.addWeighted(img.astype(np.float32), 0.72, overlay, 0.28, 0)
    return np.clip(out, 0, 255).astype(np.uint8)


def horizontal_flip_boxes(boxes: list[list[float]]) -> list[list[float]]:
    return [[cls, 1.0 - x, y, w, h] for cls, x, y, w, h in boxes]


def augment_train_set(manifest_items: list[dict]) -> dict:
    train_items = [x for x in manifest_items if x["split"] == "train"]
    counts = {"augmented_images": 0, "augmented_boxes": 0}
    recipes = [
        ("dark", lambda img: adjust_light(img, alpha=0.72, beta=-18, gamma=1.25), False),
        ("bright", lambda img: adjust_light(img, alpha=1.22, beta=22, gamma=0.82), False),
        ("shadow", add_shadow, False),
        ("glare", add_glare, False),
        ("blur", lambda img: cv2.GaussianBlur(img, (5, 5), 0), False),
        ("flip", lambda img: cv2.flip(img, 1), True),
    ]
    random.seed(RANDOM_SEED)
    for item in train_items:
        img_path = Path(item["image"])
        label_path = Path(item["label"])
        boxes = read_label(label_path)
        if not boxes:
            continue
        img = load_image(img_path)
        for suffix, func, flip_boxes in recipes:
            out_img = func(img.copy())
            out_boxes = horizontal_flip_boxes(boxes) if flip_boxes else boxes
            dst_img = img_path.with_name(f"{img_path.stem}_aug_{suffix}{img_path.suffix}")
            dst_label = label_path.with_name(f"{label_path.stem}_aug_{suffix}.txt")
            save_image(dst_img, out_img)
            write_label(dst_label, out_boxes)
            counts["augmented_images"] += 1
            counts["augmented_boxes"] += len(out_boxes)
    return counts


def write_data_yaml() -> None:
    data = {
        "path": str(OUT).replace("\\", "/"),
        "train": "images/train",
        "val": "images/val",
        "test": "",
        "names": {0: "parcel"},
    }
    (OUT / "data.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def summarize_dataset() -> dict:
    summary: dict[str, dict] = {}
    for split in ["train", "val"]:
        image_dir = OUT / "images" / split
        label_dir = OUT / "labels" / split
        images = [p for p in image_dir.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES] if image_dir.exists() else []
        labels = list(label_dir.rglob("*.txt")) if label_dir.exists() else []
        box_count = 0
        bad_labels = []
        for label in labels:
            for line in label.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if len(parts) != 5:
                    bad_labels.append(str(label))
                    continue
                cls, x, y, w, h = [float(v) for v in parts]
                if cls != 0 or not all(math.isfinite(v) for v in [x, y, w, h]) or not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    bad_labels.append(str(label))
                box_count += 1
        summary[split] = {"images": len(images), "labels": len(labels), "boxes": box_count, "bad_labels": sorted(set(bad_labels))[:20]}
    return summary


def main() -> None:
    ensure_dir(SOURCES)
    for part in ["images/train", "images/val", "labels/train", "labels/val"]:
        ensure_dir(OUT / part)

    manifest_items: list[dict] = []
    report = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target": str(OUT),
        "class_map": {"0": "parcel"},
        "sources": {
            "PackDet": {
                "url": "https://huggingface.co/datasets/industoai/PackDet",
                "license": "CC BY-NC 4.0",
            },
            "Open Images validation": {
                "url": "https://storage.googleapis.com/openimages/web/download.html",
                "license": "image-level licenses from source metadata, commonly CC BY 2.0 on downloaded validation records",
                "included_labels": OPENIMAGES_LABELS,
                "max_images": OPENIMAGES_MAX_IMAGES,
            },
        },
    }

    report["packdet_download"] = download_packdet()
    report["packdet_collect"] = collect_packdet(manifest_items)
    report["openimages_collect"] = collect_openimages(manifest_items)
    report["augmentation"] = augment_train_set(manifest_items)
    write_data_yaml()
    report["summary"] = summarize_dataset()
    report["manifest_items"] = manifest_items[:50]

    (OUT / "dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
