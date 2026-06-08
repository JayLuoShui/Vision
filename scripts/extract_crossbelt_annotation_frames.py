import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "datasets" / "cvds_crossbelt_annotation_seed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从交叉带视频抽帧，生成真实场景标注种子集")
    parser.add_argument("--source", required=True, help="交叉带视频")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出目录")
    parser.add_argument("--count", type=int, default=120, help="抽帧数量")
    parser.add_argument("--start-frame", type=int, default=0, help="起始帧")
    parser.add_argument("--end-frame", type=int, default=None, help="结束帧；不填则到视频末尾")
    parser.add_argument("--prefix", default="crossbelt", help="输出图片前缀")
    return parser.parse_args()


def save_image(path: Path, img) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".jpg", img)
    if not ok:
        raise RuntimeError(f"写入图片失败：{path}")
    data.tofile(str(path))


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    output = Path(args.output)
    image_dir = output / "images"
    manifest = output / "manifest.csv"
    if image_dir.exists() and any(image_dir.glob("*.jpg")):
        raise FileExistsError(f"输出目录已有图片：{image_dir}")

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频：{source}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    start = max(0, min(args.start_frame, max(0, frame_count - 1)))
    end = args.end_frame if args.end_frame is not None else frame_count - 1
    end = max(start, min(end, max(0, frame_count - 1)))
    indices = np.linspace(start, end, args.count, dtype=int).tolist()

    rows = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if not ok:
            continue
        name = f"{args.prefix}_{idx:06d}.jpg"
        save_image(image_dir / name, frame)
        rows.append(
            {
                "image": name,
                "frame": idx,
                "time_sec": round(idx / fps, 3) if fps else "",
                "width": width,
                "height": height,
                "source": str(source),
                "label_status": "need_manual_box",
            }
        )
    cap.release()

    output.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "frame", "time_sec", "width", "height", "source", "label_status"])
        writer.writeheader()
        writer.writerows(rows)
    readme = [
        "# 交叉带真实场景标注种子集",
        "",
        "这些图片来自真实交叉带视频，只做抽帧，不自动生成框。",
        "下一步需要人工标注包裹整体框，类别统一写 `parcel`。",
        "完成标注后再合并进 YOLO 数据集训练。",
        "",
        f"视频：{source}",
        f"抽帧范围：{start} 到 {end}",
        f"输出图片：{len(rows)} 张",
    ]
    (output / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print({"output": str(output), "images": len(rows), "manifest": str(manifest)})


if __name__ == "__main__":
    main()
