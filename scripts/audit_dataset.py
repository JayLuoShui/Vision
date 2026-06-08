import argparse
import csv
import random
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLIT_NAMES = {"train", "val", "test"}


@dataclass(frozen=True)
class BBoxRecord:
    image_path: Path
    label_path: Path
    split: str
    class_id: int
    bbox_xywh: tuple[float, float, float, float]
    area_ratio: float


@dataclass(frozen=True)
class ImageRecord:
    image_path: Path
    label_path: Path
    split: str
    bbox_count: int
    group_id: str


@dataclass(frozen=True)
class AuditSummary:
    total_images: int
    annotated_images: int
    empty_label_images: int
    total_bboxes: int
    large_bbox_count: int
    huge_bbox_count: int
    leakage_group_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="审计 YOLO parcel 数据集的大框、空帧和 split 泄漏风险")
    parser.add_argument("--dataset", required=True, type=Path, help="YOLO 数据集根目录")
    parser.add_argument("--output", required=True, type=Path, help="审计输出目录")
    parser.add_argument("--large-threshold", type=float, default=0.2, help="大框面积比例阈值")
    parser.add_argument("--huge-threshold", type=float, default=0.4, help="严重大框面积比例阈值")
    parser.add_argument("--sample-empty", type=int, default=5000, help="抽样空标签图片数量")
    parser.add_argument("--seed", type=int, default=20260509, help="随机种子")
    parser.add_argument(
        "--group-mode",
        choices=["video-id", "prefix", "regex", "none"],
        default="video-id",
        help="group split 的分组方式",
    )
    parser.add_argument("--group-prefix-parts", type=int, default=2, help="prefix 模式使用文件名前几个下划线片段")
    parser.add_argument("--group-regex", default=None, help="regex 模式的分组正则，优先取第一个捕获组")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="group split 建议 train 比例")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="group split 建议 val 比例")
    return parser.parse_args()


def audit_dataset(
    dataset: Path,
    output: Path,
    large_threshold: float,
    huge_threshold: float,
    sample_empty: int,
    seed: int = 20260509,
    group_mode: str = "video-id",
    group_prefix_parts: int = 2,
    group_regex: str | None = None,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
) -> AuditSummary:
    dataset = dataset.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    image_records, bbox_records = scan_yolo_dataset(dataset, group_mode, group_prefix_parts, group_regex)
    write_bbox_stats(output / "bbox_area_stats.csv", bbox_records)
    copy_large_samples(output, bbox_records, large_threshold, "large_bbox_over_20")
    copy_large_samples(output, bbox_records, huge_threshold, "large_bbox_over_40")
    copy_negative_samples(output, image_records, sample_empty, seed)
    leakage_rows = write_group_split_leakage(output / "group_split_leakage.csv", image_records)
    write_group_split_suggestion(
        output / "group_split_suggestion.csv",
        image_records,
        seed=seed,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
    )
    split_stats = split_positive_negative_stats(image_records)

    summary = AuditSummary(
        total_images=len(image_records),
        annotated_images=sum(1 for item in image_records if item.bbox_count > 0),
        empty_label_images=sum(1 for item in image_records if item.bbox_count == 0),
        total_bboxes=len(bbox_records),
        large_bbox_count=sum(1 for item in bbox_records if item.area_ratio > large_threshold),
        huge_bbox_count=sum(1 for item in bbox_records if item.area_ratio > huge_threshold),
        leakage_group_count=sum(1 for item in leakage_rows if item["leakage_risk"] == "yes"),
    )
    write_quality_report(
        output / "dataset_quality_report.md",
        dataset=dataset,
        output=output,
        summary=summary,
        split_stats=split_stats,
        large_threshold=large_threshold,
        huge_threshold=huge_threshold,
        sample_empty=sample_empty,
    )
    return summary


def scan_yolo_dataset(
    dataset: Path,
    group_mode: str,
    group_prefix_parts: int,
    group_regex: str | None,
) -> tuple[list[ImageRecord], list[BBoxRecord]]:
    image_root = dataset / "images"
    if not image_root.exists():
        raise FileNotFoundError(f"找不到 images 目录：{image_root}")

    image_records: list[ImageRecord] = []
    bbox_records: list[BBoxRecord] = []
    for image_path in sorted(iter_images(image_root), key=lambda path: str(path).lower()):
        split = split_for_image(image_path, image_root)
        label_path = label_path_for_image(dataset, image_path)
        boxes = read_yolo_boxes(label_path)
        group_id = group_id_for_image(image_path, group_mode, group_prefix_parts, group_regex)
        image_records.append(
            ImageRecord(
                image_path=image_path,
                label_path=label_path,
                split=split,
                bbox_count=len(boxes),
                group_id=group_id,
            )
        )
        for class_id, xywh in boxes:
            area_ratio = xywh[2] * xywh[3]
            bbox_records.append(
                BBoxRecord(
                    image_path=image_path,
                    label_path=label_path,
                    split=split,
                    class_id=class_id,
                    bbox_xywh=xywh,
                    area_ratio=area_ratio,
                )
            )
    return image_records, bbox_records


def iter_images(image_root: Path) -> list[Path]:
    return [path for path in image_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]


def split_for_image(image_path: Path, image_root: Path) -> str:
    relative = image_path.relative_to(image_root)
    if len(relative.parts) > 1 and relative.parts[0] in SPLIT_NAMES:
        return relative.parts[0]
    return "all"


def label_path_for_image(dataset: Path, image_path: Path) -> Path:
    image_root = dataset / "images"
    relative = image_path.relative_to(image_root)
    return (dataset / "labels" / relative).with_suffix(".txt")


def read_yolo_boxes(label_path: Path) -> list[tuple[int, tuple[float, float, float, float]]]:
    if not label_path.exists():
        return []
    boxes: list[tuple[int, tuple[float, float, float, float]]] = []
    for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            continue
        class_id = int(float(parts[0]))
        x, y, w, h = [float(value) for value in parts[1:]]
        boxes.append((class_id, (x, y, w, h)))
    return boxes


def group_id_for_image(
    image_path: Path,
    group_mode: str,
    group_prefix_parts: int,
    group_regex: str | None,
) -> str:
    stem = image_path.stem
    if group_mode == "none":
        return stem
    if group_mode == "regex":
        if not group_regex:
            raise ValueError("group-mode=regex 时必须提供 --group-regex")
        match = re.search(group_regex, stem)
        if not match:
            raise ValueError(f"文件名不匹配 group-regex：{stem}")
        return match.group(1) if match.groups() else match.group(0)
    if group_mode == "prefix":
        parts = stem.split("_")
        return "_".join(parts[: max(1, group_prefix_parts)])
    if group_mode == "video-id":
        return re.sub(r"[_-]?\d+$", "", stem)
    raise ValueError(f"未知 group-mode：{group_mode}")


def write_bbox_stats(path: Path, bbox_records: list[BBoxRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["image_path", "label_path", "class_id", "bbox_xywh", "area_ratio"],
        )
        writer.writeheader()
        for item in bbox_records:
            writer.writerow(
                {
                    "image_path": str(item.image_path),
                    "label_path": str(item.label_path),
                    "class_id": item.class_id,
                    "bbox_xywh": format_xywh(item.bbox_xywh),
                    "area_ratio": f"{item.area_ratio:.8f}",
                }
            )


def copy_large_samples(output: Path, bbox_records: list[BBoxRecord], threshold: float, folder_name: str) -> None:
    records_by_image: dict[Path, list[BBoxRecord]] = {}
    for item in bbox_records:
        if item.area_ratio > threshold:
            records_by_image.setdefault(item.image_path, []).append(item)
    for image_path, records in records_by_image.items():
        split = records[0].split
        dst_image = output / folder_name / "images" / split / image_path.name
        dst_label = output / folder_name / "labels" / split / records[0].label_path.name
        dst_viz = output / folder_name / "visualizations" / split / f"{image_path.stem}_viz.jpg"
        copy_file(image_path, dst_image)
        if records[0].label_path.exists():
            copy_file(records[0].label_path, dst_label)
        else:
            write_text(dst_label, "")
        draw_visualization(image_path, records, dst_viz)


def copy_negative_samples(output: Path, image_records: list[ImageRecord], sample_empty: int, seed: int) -> None:
    empty_images = [item for item in image_records if item.bbox_count == 0]
    rng = random.Random(seed)
    selected = rng.sample(empty_images, min(sample_empty, len(empty_images))) if sample_empty > 0 else []
    for item in selected:
        dst_image = output / "negative_samples" / "images" / item.split / item.image_path.name
        dst_label = output / "negative_samples" / "labels" / item.split / item.label_path.name
        copy_file(item.image_path, dst_image)
        if item.label_path.exists():
            copy_file(item.label_path, dst_label)
        else:
            write_text(dst_label, "")


def draw_visualization(image_path: Path, records: list[BBoxRecord], output_path: Path) -> None:
    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"图片读取失败：{image_path}")
    height, width = image.shape[:2]
    for item in records:
        x, y, w, h = item.bbox_xywh
        x1 = int((x - w / 2) * width)
        y1 = int((y - h / 2) * height)
        x2 = int((x + w / 2) * width)
        y2 = int((y + h / 2) * height)
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(
            image,
            f"cls={item.class_id} area={item.area_ratio:.3f}",
            (max(0, x1), max(20, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 0, 255),
            2,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".jpg", image)
    if not ok:
        raise RuntimeError(f"可视化写入失败：{output_path}")
    data.tofile(str(output_path))


def write_group_split_leakage(path: Path, image_records: list[ImageRecord]) -> list[dict[str, str]]:
    groups: dict[str, list[ImageRecord]] = {}
    for item in image_records:
        groups.setdefault(item.group_id, []).append(item)
    rows = []
    for group_id, records in sorted(groups.items()):
        splits = sorted({item.split for item in records})
        rows.append(
            {
                "group_id": group_id,
                "splits": "|".join(splits),
                "image_count": str(len(records)),
                "positive_count": str(sum(1 for item in records if item.bbox_count > 0)),
                "empty_count": str(sum(1 for item in records if item.bbox_count == 0)),
                "leakage_risk": "yes" if len(splits) > 1 else "no",
            }
        )
    write_dict_rows(path, ["group_id", "splits", "image_count", "positive_count", "empty_count", "leakage_risk"], rows)
    return rows


def write_group_split_suggestion(
    path: Path,
    image_records: list[ImageRecord],
    seed: int,
    train_ratio: float,
    val_ratio: float,
) -> None:
    groups: dict[str, list[ImageRecord]] = {}
    for item in image_records:
        groups.setdefault(item.group_id, []).append(item)
    group_items = list(groups.items())
    random.Random(seed).shuffle(group_items)
    total_images = sum(len(records) for _, records in group_items)
    train_target = total_images * train_ratio
    val_target = total_images * val_ratio
    assigned_counts = {"train": 0, "val": 0, "test": 0}
    rows = []
    for group_id, records in group_items:
        if assigned_counts["train"] < train_target:
            split = "train"
        elif assigned_counts["val"] < val_target:
            split = "val"
        else:
            split = "test"
        assigned_counts[split] += len(records)
        rows.append(
            {
                "group_id": group_id,
                "suggested_split": split,
                "image_count": str(len(records)),
                "positive_count": str(sum(1 for item in records if item.bbox_count > 0)),
                "empty_count": str(sum(1 for item in records if item.bbox_count == 0)),
            }
        )
    rows.sort(key=lambda row: row["group_id"])
    write_dict_rows(path, ["group_id", "suggested_split", "image_count", "positive_count", "empty_count"], rows)


def split_positive_negative_stats(image_records: list[ImageRecord]) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    for item in image_records:
        row = stats.setdefault(item.split, {"total": 0, "positive": 0, "empty": 0})
        row["total"] += 1
        if item.bbox_count > 0:
            row["positive"] += 1
        else:
            row["empty"] += 1
    return stats


def write_quality_report(
    path: Path,
    dataset: Path,
    output: Path,
    summary: AuditSummary,
    split_stats: dict[str, dict[str, int]],
    large_threshold: float,
    huge_threshold: float,
    sample_empty: int,
) -> None:
    lines = [
        "# Dataset Quality Report",
        "",
        f"- 数据集：`{dataset}`",
        f"- 输出目录：`{output}`",
        f"- 大框阈值：`{large_threshold}`",
        f"- 严重大框阈值：`{huge_threshold}`",
        f"- 空标签抽样数量：`{sample_empty}`",
        "",
        "## 总览",
        "",
        f"- 总图片数：{summary.total_images}",
        f"- 有标注图片数：{summary.annotated_images}",
        f"- 空标签图片数：{summary.empty_label_images}",
        f"- 总 bbox 数：{summary.total_bboxes}",
        f"- >20% 大框数量：{summary.large_bbox_count}",
        f"- >40% 大框数量：{summary.huge_bbox_count}",
        f"- group split 泄漏风险组数：{summary.leakage_group_count}",
        "",
        "## 每个 split 的正负样本比例",
        "",
        "| split | total | positive | empty | positive_ratio | empty_ratio |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for split, row in sorted(split_stats.items()):
        total = row["total"]
        positive_ratio = row["positive"] / total if total else 0.0
        empty_ratio = row["empty"] / total if total else 0.0
        lines.append(
            f"| {split} | {total} | {row['positive']} | {row['empty']} | {positive_ratio:.4f} | {empty_ratio:.4f} |"
        )
    lines.extend(
        [
            "",
            "## 输出文件",
            "",
            "- `bbox_area_stats.csv`：所有 bbox 的面积比例明细。",
            "- `large_bbox_over_20/`：面积比例超过 20% 的疑似大框样本和可视化图。",
            "- `large_bbox_over_40/`：面积比例超过 40% 的严重疑似大框样本和可视化图。",
            "- `negative_samples/`：从空标签图片中随机抽样的负样本。",
            "- `group_split_leakage.csv`：同一 group 是否出现在多个 split。",
            "- `group_split_suggestion.csv`：不打散 group 的 split 建议表。",
        ]
    )
    write_text(path, "\n".join(lines) + "\n")


def write_dict_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def format_xywh(xywh: tuple[float, float, float, float]) -> str:
    return " ".join(f"{value:.6f}" for value in xywh)


def main() -> int:
    args = parse_args()
    summary = audit_dataset(
        dataset=args.dataset,
        output=args.output,
        large_threshold=args.large_threshold,
        huge_threshold=args.huge_threshold,
        sample_empty=args.sample_empty,
        seed=args.seed,
        group_mode=args.group_mode,
        group_prefix_parts=args.group_prefix_parts,
        group_regex=args.group_regex,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
    )
    print(f"完成审计：图片 {summary.total_images} 张，bbox {summary.total_bboxes} 个")
    print(f">20% 大框 {summary.large_bbox_count} 个，>40% 大框 {summary.huge_bbox_count} 个")
    print(f"group split 泄漏风险组 {summary.leakage_group_count} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
