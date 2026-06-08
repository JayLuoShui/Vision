import argparse
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
DEFAULT_SOURCE = ROOT / "datasets" / "cvds_package_yolo26"
DEFAULT_OUTPUT = ROOT / "datasets" / "cvds_package_yolo26_crossbelt"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
RANDOM_SEED = 20260507


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成更适合交叉带视频的小目标包裹训练集")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="原 YOLO 包裹数据集目录")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出数据集目录")
    parser.add_argument("--variants", type=int, default=2, help="每张原始训练图生成几个交叉带小目标增强样本")
    parser.add_argument("--width", type=int, default=960, help="增强图宽度")
    parser.add_argument("--height", type=int, default=540, help="增强图高度")
    parser.add_argument("--grabcut", action="store_true", help="使用 GrabCut 抠前景，质量更高但速度很慢")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已有输出目录")
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"读取图片失败：{path}")
    return img


def save_image(path: Path, img: np.ndarray) -> None:
    ensure_dir(path.parent)
    ok, data = cv2.imencode(path.suffix.lower(), img)
    if not ok:
        raise RuntimeError(f"写入图片失败：{path}")
    data.tofile(str(path))


def read_label(path: Path) -> list[list[float]]:
    boxes = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) == 5:
            boxes.append([int(float(parts[0]))] + [float(x) for x in parts[1:]])
    return boxes


def write_label(path: Path, boxes: list[list[float]]) -> None:
    ensure_dir(path.parent)
    text = "\n".join(f"{int(c)} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for c, x, y, w, h in boxes)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def image_for_label(image_dir: Path, stem: str) -> Path | None:
    for suffix in IMAGE_SUFFIXES:
        candidate = image_dir / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def copy_dataset(source: Path, output: Path) -> None:
    for rel in ["images/train", "images/val", "images/test", "labels/train", "labels/val", "labels/test"]:
        src = source / rel
        dst = output / rel
        ensure_dir(dst)
        for file in src.iterdir():
            if file.is_file():
                shutil.copy2(file, dst / file.name)


def make_conveyor_background(width: int, height: int) -> np.ndarray:
    base = np.zeros((height, width, 3), dtype=np.uint8)
    gray = random.randint(58, 92)
    base[:] = (gray, gray + random.randint(-6, 6), gray + random.randint(-6, 6))
    noise = np.random.normal(0, 8, base.shape).astype(np.float32)
    base = np.clip(base.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    belt_y1 = random.randint(int(height * 0.22), int(height * 0.38))
    belt_y2 = random.randint(int(height * 0.70), int(height * 0.88))
    cv2.rectangle(base, (0, belt_y1), (width, belt_y2), (42, 49, 52), -1)
    for x in range(-width, width * 2, random.randint(70, 120)):
        cv2.line(base, (x, belt_y1), (x + width // 5, belt_y2), (74, 80, 84), 2)
    rail_color = random.choice([(38, 45, 150), (20, 90, 170), (50, 120, 180)])
    cv2.line(base, (0, belt_y1), (width, belt_y1 + random.randint(-8, 8)), rail_color, random.randint(5, 9))
    cv2.line(base, (0, belt_y2), (width, belt_y2 + random.randint(-8, 8)), rail_color, random.randint(5, 9))
    return cv2.GaussianBlur(base, (3, 3), 0)


def extract_foreground(crop: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h, w = crop.shape[:2]
    if h < 12 or w < 12:
        raise RuntimeError("包裹裁剪区域太小，无法做前景增强")
    mask = np.zeros((h, w), dtype=np.uint8)
    bg_model = np.zeros((1, 65), dtype=np.float64)
    fg_model = np.zeros((1, 65), dtype=np.float64)
    rect = (max(1, w // 12), max(1, h // 12), max(2, w - w // 6), max(2, h - h // 6))
    cv2.grabCut(crop, mask, rect, bg_model, fg_model, 3, cv2.GC_INIT_WITH_RECT)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8), iterations=1)
    ys, xs = np.where(fg > 0)
    if len(xs) < 30:
        raise RuntimeError("包裹前景提取失败")
    x1 = max(0, int(xs.min()) - 2)
    y1 = max(0, int(ys.min()) - 2)
    x2 = min(w, int(xs.max()) + 3)
    y2 = min(h, int(ys.max()) + 3)
    obj = crop[y1:y2, x1:x2]
    obj_mask = fg[y1:y2, x1:x2]
    if obj.size == 0 or obj_mask.mean() < 8:
        raise RuntimeError("包裹前景面积异常")
    return obj, obj_mask


def yolo_to_xyxy(box: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    _, x, y, bw, bh = box
    x1 = max(0, int((x - bw / 2) * width))
    y1 = max(0, int((y - bh / 2) * height))
    x2 = min(width, int((x + bw / 2) * width))
    y2 = min(height, int((y + bh / 2) * height))
    return x1, y1, x2, y2


def paste_small_scene(img: np.ndarray, boxes: list[list[float]], width: int, height: int, use_grabcut: bool) -> tuple[np.ndarray, list[list[float]]]:
    src_h, src_w = img.shape[:2]
    canvas = make_conveyor_background(width, height)
    out_boxes: list[list[float]] = []
    shuffled = boxes[:]
    random.shuffle(shuffled)

    for box in shuffled[: min(len(shuffled), random.randint(1, 3))]:
        x1, y1, x2, y2 = yolo_to_xyxy(box, src_w, src_h)
        pad_ratio = 0.14 if use_grabcut else 0.01
        pad_x = max(1, int((x2 - x1) * pad_ratio))
        pad_y = max(1, int((y2 - y1) * pad_ratio))
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(src_w, x2 + pad_x)
        y2 = min(src_h, y2 + pad_y)
        crop = img[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        if use_grabcut:
            try:
                crop, crop_mask = extract_foreground(crop)
            except RuntimeError:
                continue
        else:
            crop_mask = np.full(crop.shape[:2], 255, dtype=np.uint8)

        aspect = crop.shape[1] / max(1, crop.shape[0])
        target_w = random.randint(int(width * 0.08), int(width * 0.24))
        target_h = max(18, int(target_w / max(0.25, aspect)))
        if target_h > int(height * 0.26):
            target_h = int(height * 0.26)
            target_w = max(18, int(target_h * aspect))
        if target_w >= width or target_h >= height:
            continue

        resized = cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_AREA)
        mask = cv2.resize(crop_mask, (target_w, target_h), interpolation=cv2.INTER_AREA)
        alpha = random.uniform(0.78, 1.18)
        beta = random.uniform(-18, 18)
        resized = cv2.convertScaleAbs(resized, alpha=alpha, beta=beta)
        if random.random() < 0.35:
            resized = cv2.GaussianBlur(resized, (3, 3), 0)

        px = random.randint(0, width - target_w)
        py = random.randint(int(height * 0.28), max(int(height * 0.28), height - target_h - 8))
        mask = cv2.GaussianBlur(mask, (3, 3), 0).astype(np.float32) / 255.0
        roi = canvas[py : py + target_h, px : px + target_w].astype(np.float32)
        blended = resized.astype(np.float32) * mask[..., None] + roi * (1.0 - mask[..., None])
        canvas[py : py + target_h, px : px + target_w] = np.clip(blended, 0, 255).astype(np.uint8)
        out_boxes.append(
            [
                0,
                (px + target_w / 2) / width,
                (py + target_h / 2) / height,
                target_w / width,
                target_h / height,
            ]
        )

    if not out_boxes:
        raise RuntimeError("交叉带小目标增强没有生成有效标注")
    return canvas, out_boxes


def augment_crossbelt(source: Path, output: Path, variants: int, width: int, height: int, use_grabcut: bool) -> dict:
    image_dir = source / "images" / "train"
    label_dir = source / "labels" / "train"
    out_image_dir = output / "images" / "train"
    out_label_dir = output / "labels" / "train"
    stats = {"images": 0, "boxes": 0}
    for label in sorted(label_dir.glob("*.txt")):
        if "_aug_" in label.stem:
            continue
        img_path = image_for_label(image_dir, label.stem)
        if img_path is None:
            continue
        boxes = read_label(label)
        if not boxes:
            continue
        img = load_image(img_path)
        for idx in range(variants):
            try:
                scene, scene_boxes = paste_small_scene(img, boxes, width, height, use_grabcut)
            except RuntimeError:
                continue
            stem = f"{label.stem}_crossbelt_small_{idx + 1}"
            save_image(out_image_dir / f"{stem}.jpg", scene)
            write_label(out_label_dir / f"{stem}.txt", scene_boxes)
            stats["images"] += 1
            stats["boxes"] += len(scene_boxes)
    return stats


def validate(output: Path) -> dict:
    summary = {}
    for split in ["train", "val", "test"]:
        image_dir = output / "images" / split
        label_dir = output / "labels" / split
        images = [p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES]
        labels = list(label_dir.glob("*.txt"))
        bad = []
        boxes = 0
        for label in labels:
            for line in label.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    bad.append(str(label))
                    continue
                values = [float(x) for x in parts]
                _, x, y, w, h = values
                if not all(math.isfinite(v) for v in values) or not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    bad.append(str(label))
                boxes += 1
        summary[split] = {"images": len(images), "labels": len(labels), "boxes": boxes, "bad_labels": sorted(set(bad))[:20]}
    return summary


def write_yaml(output: Path) -> None:
    data = {
        "path": str(output).replace("\\", "/"),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {0: "parcel"},
    }
    (output / "data.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main() -> None:
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    args = parse_args()
    source = Path(args.source)
    output = Path(args.output)
    if output.exists():
        if not args.overwrite:
            raise FileExistsError(f"输出目录已存在：{output}。如需覆盖，显式传入 --overwrite")
        shutil.rmtree(output)
    copy_dataset(source, output)
    aug_stats = augment_crossbelt(source, output, args.variants, args.width, args.height, args.grabcut)
    write_yaml(output)
    summary = validate(output)
    report = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(source),
        "output": str(output),
        "reason": "交叉带视频中的包裹更小，且背景是输送设备；本数据集补充小目标和输送带背景增强样本。",
        "grabcut": args.grabcut,
        "crossbelt_augmentation": aug_stats,
        "summary": summary,
    }
    (output / "dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
