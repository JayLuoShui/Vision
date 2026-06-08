import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = ROOT / "weights" / "cvds_yolo26n_package_best.pt"
DEFAULT_DATASET = ROOT / "datasets" / "cvds_package_yolo26"
DEFAULT_OUTPUT = ROOT / "runs" / "video_diagnosis"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="诊断包裹模型在现场视频上的尺寸和泛化问题")
    parser.add_argument("--source", required=True, help="待诊断视频")
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS), help="模型权重")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="YOLO 数据集目录")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="诊断输出目录")
    parser.add_argument("--device", default="0", help="推理设备")
    parser.add_argument("--conf", type=float, default=0.15, help="采样诊断置信度")
    parser.add_argument("--samples", type=int, default=30, help="采样帧数量")
    parser.add_argument("--imgsz", default="640,960,1280", help="逗号分隔的推理尺寸")
    parser.add_argument("--start-frame", type=int, default=0, help="采样起始帧")
    parser.add_argument("--end-frame", type=int, default=None, help="采样结束帧；不填则到视频末尾")
    parser.add_argument("--detect-roi", default=None, help="只在该区域检测：x1,y1,x2,y2 或多边形点列表")
    return parser.parse_args()


def parse_point_list(text: str | None) -> list[tuple[int, int]] | None:
    if not text:
        return None
    values = [int(float(x.strip())) for x in text.split(",") if x.strip()]
    if len(values) < 4 or len(values) % 2 != 0:
        raise ValueError("--detect-roi 必须是 x1,y1,x2,y2 或多边形点列表")
    return [(values[i], values[i + 1]) for i in range(0, len(values), 2)]


def crop_by_roi(frame: np.ndarray, polygon: list[tuple[int, int]] | None) -> tuple[np.ndarray, tuple[int, int], tuple[int, int, int, int] | None]:
    if not polygon:
        return frame, (0, 0), None
    height, width = frame.shape[:2]
    contour = np.array(polygon, dtype=np.int32)
    x, y, w, h = cv2.boundingRect(contour)
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(width, x + w)
    y2 = min(height, y + h)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("--detect-roi 超出画面或面积为 0")
    return frame[y1:y2, x1:x2], (x1, y1), (x1, y1, x2, y2)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * p / 100
    low = math.floor(k)
    high = math.ceil(k)
    if low == high:
        return ordered[int(k)]
    return ordered[low] * (high - k) + ordered[high] * (k - low)


def summarize(values: list[float]) -> dict:
    return {
        "count": len(values),
        "p10": percentile(values, 10),
        "p50": percentile(values, 50),
        "p90": percentile(values, 90),
    }


def dataset_label_stats(dataset: Path) -> dict:
    widths: list[float] = []
    heights: list[float] = []
    areas: list[float] = []
    for split in ["train", "val", "test"]:
        for label in (dataset / "labels" / split).glob("*.txt"):
            for line in label.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                bw = float(parts[3])
                bh = float(parts[4])
                widths.append(bw)
                heights.append(bh)
                areas.append(bw * bh)
    return {
        "width": summarize(widths),
        "height": summarize(heights),
        "area": summarize(areas),
    }


def draw_preview(
    model: YOLO,
    frames: list[tuple[int, np.ndarray]],
    output: Path,
    imgsz: int,
    conf: float,
    device: str,
    detect_roi: list[tuple[int, int]] | None,
) -> str | None:
    cells = []
    for frame_idx, frame in frames:
        infer_frame, offset, roi_rect = crop_by_roi(frame, detect_roi)
        result = model.predict(infer_frame, imgsz=imgsz, conf=conf, device=device, verbose=False)[0]
        annotated = frame.copy()
        count = 0
        if result.boxes is not None:
            for box, score, cls in zip(
                result.boxes.xyxy.cpu().numpy(),
                result.boxes.conf.cpu().numpy(),
                result.boxes.cls.cpu().numpy(),
            ):
                if int(cls) != 0:
                    continue
                x1, y1, x2, y2 = [int(v) for v in box]
                x1 += offset[0]
                x2 += offset[0]
                y1 += offset[1]
                y2 += offset[1]
                count += 1
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 220, 0), 2)
                cv2.putText(annotated, f"{score:.2f}", (x1, max(20, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 0), 2)
        if roi_rect:
            x1, y1, x2, y2 = roi_rect
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 160, 0), 2)
        cv2.putText(annotated, f"frame {frame_idx} det {count}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 4)
        cv2.putText(annotated, f"frame {frame_idx} det {count}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
        cells.append(cv2.resize(annotated, (320, 180)))
    if not cells:
        return None
    rows = []
    for i in range(0, len(cells), 4):
        row = cells[i : i + 4]
        while len(row) < 4:
            row.append(np.zeros_like(cells[0]))
        rows.append(np.hstack(row))
    preview = np.vstack(rows)
    path = output / f"preview_imgsz{imgsz}.jpg"
    cv2.imwrite(str(path), preview)
    return str(path)


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    imgsz_values = [int(x.strip()) for x in args.imgsz.split(",") if x.strip()]

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频：{source}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    end_frame = args.end_frame if args.end_frame is not None else frame_count - 1
    start_frame = max(0, min(args.start_frame, frame_count - 1))
    end_frame = max(start_frame, min(end_frame, frame_count - 1))
    sample_indices = np.linspace(start_frame, end_frame, args.samples, dtype=int).tolist()
    detect_roi = parse_point_list(args.detect_roi)

    model = YOLO(args.weights)
    stats = {imgsz: {"frames_with_det": 0, "boxes": 0, "conf": [], "area": []} for imgsz in imgsz_values}
    preview_frames: list[tuple[int, np.ndarray]] = []
    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if not ok:
            continue
        if len(preview_frames) < 8:
            preview_frames.append((idx, frame.copy()))
        for imgsz in imgsz_values:
            infer_frame, offset, _ = crop_by_roi(frame, detect_roi)
            result = model.predict(infer_frame, imgsz=imgsz, conf=args.conf, device=args.device, verbose=False)[0]
            frame_boxes = 0
            if result.boxes is not None:
                for box, score, cls in zip(
                    result.boxes.xyxy.cpu().numpy(),
                    result.boxes.conf.cpu().numpy(),
                    result.boxes.cls.cpu().numpy(),
                ):
                    if int(cls) != 0:
                        continue
                    x1, y1, x2, y2 = box
                    x1 += offset[0]
                    x2 += offset[0]
                    y1 += offset[1]
                    y2 += offset[1]
                    frame_boxes += 1
                    stats[imgsz]["conf"].append(float(score))
                    stats[imgsz]["area"].append(float((x2 - x1) * (y2 - y1) / (width * height)))
            stats[imgsz]["boxes"] += frame_boxes
            if frame_boxes:
                stats[imgsz]["frames_with_det"] += 1
    cap.release()

    for imgsz in imgsz_values:
        item = stats[imgsz]
        item["sample_frames"] = len(sample_indices)
        item["frames_with_det_ratio"] = item["frames_with_det"] / max(1, len(sample_indices))
        item["conf_summary"] = summarize(item.pop("conf"))
        item["area_summary"] = summarize(item.pop("area"))

    preview = draw_preview(model, preview_frames, output, max(imgsz_values), args.conf, args.device, detect_roi)
    report = {
        "video": {
            "path": str(source),
            "width": width,
            "height": height,
            "fps": fps,
            "frames": frame_count,
            "duration_sec": frame_count / fps if fps else 0,
            "sample_start_frame": start_frame,
            "sample_end_frame": end_frame,
        },
        "detect_roi": args.detect_roi,
        "model_sampling": stats,
        "dataset_label_stats": dataset_label_stats(Path(args.dataset)),
        "preview": preview,
        "conclusion": "如果不同 imgsz 命中率都低，主要问题是训练集场景和目标尺寸不匹配，不是单纯视频输入尺寸错误。",
    }
    (output / "diagnosis_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
