import argparse
import csv
import json
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from ultralytics import YOLO


@dataclass
class FlowEvent:
    frame: int
    track_id: int
    event_type: str
    flow_count: int
    x: float
    y: float
    inside_count: int


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def write_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_point_list(text: str) -> list[tuple[int, int]]:
    values = [int(float(x.strip())) for x in text.split(",") if x.strip()]
    if len(values) < 6 or len(values) % 2 != 0:
        raise ValueError("ROI 坐标必须是 x1,y1,x2,y2,x3,y3... 的多边形")
    return [(values[i], values[i + 1]) for i in range(0, len(values), 2)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CVDS PT 视频检测、ROI 绘制、流量监测和堵包信号")
    parser.add_argument("--weights", required=True, help="Ultralytics PT 权重")
    parser.add_argument("--source", required=True, help="视频文件、摄像头编号或 RTSP 地址")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--preview-path", required=True, help="写给 C++ 界面读取的预览 JPG")
    parser.add_argument("--roi", required=True, help="流量统计 ROI 多边形：x1,y1,x2,y2,x3,y3...")
    parser.add_argument("--detect-roi", default=None, help="只在该区域内检测，格式同 roi")
    parser.add_argument("--conf", type=float, default=0.25, help="检测置信度")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IoU")
    parser.add_argument("--imgsz", type=int, default=960, help="推理输入尺寸")
    parser.add_argument("--device", default="0", help="推理设备，例如 0 或 cpu")
    parser.add_argument("--class-id", type=int, default=-1, help="只检测指定类别；-1 表示全部类别")
    parser.add_argument("--tracker", default="bytetrack.yaml", help="Ultralytics 跟踪器配置")
    parser.add_argument("--preview-fps", type=int, default=30, help="界面预览帧率上限")
    parser.add_argument("--trail", type=int, default=40, help="轨迹显示长度")
    parser.add_argument("--jam-seconds", type=int, default=5, help="ROI 内有包裹但流量不更新超过该秒数后判定堵包")
    parser.add_argument("--jam-signal-path", default=None, help="堵包信号 JSONL 输出路径")
    parser.add_argument("--max-frames", type=int, default=0, help="最多处理帧数，0 表示完整视频")
    return parser.parse_args()


def write_image_utf8(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 86])
    if not ok:
        raise RuntimeError(f"无法编码预览图片：{path}")
    path.write_bytes(data.tobytes())


def source_to_capture(source: str) -> cv2.VideoCapture:
    if source.isdigit():
        return cv2.VideoCapture(int(source))
    return cv2.VideoCapture(source)


def point_in_roi(point: tuple[float, float], polygon: list[tuple[int, int]]) -> bool:
    contour = np.array(polygon, dtype=np.int32)
    return cv2.pointPolygonTest(contour, point, False) >= 0


def crop_by_roi(
    frame: np.ndarray,
    polygon: list[tuple[int, int]] | None,
) -> tuple[np.ndarray, tuple[int, int]]:
    if not polygon:
        return frame, (0, 0)
    height, width = frame.shape[:2]
    contour = np.array(polygon, dtype=np.int32)
    x, y, w, h = cv2.boundingRect(contour)
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(width, x + w)
    y2 = min(height, y + h)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("检测 ROI 超出画面或面积为 0")
    return frame[y1:y2, x1:x2], (x1, y1)


def draw_text(frame: np.ndarray, text: str, origin: tuple[int, int]) -> None:
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)


def draw_overlay(
    frame: np.ndarray,
    roi: list[tuple[int, int]],
    detect_roi: list[tuple[int, int]] | None,
    flow_count: int,
    inside_count: int,
    jam_active: bool,
) -> None:
    roi_color = (0, 0, 255) if jam_active else (0, 210, 255)
    cv2.polylines(frame, [np.array(roi, dtype=np.int32)], True, roi_color, 3)
    if detect_roi is not None:
        cv2.polylines(frame, [np.array(detect_roi, dtype=np.int32)], True, (255, 170, 0), 2)
    draw_text(frame, f"FLOW: {flow_count}", (24, 42))
    draw_text(frame, f"IN ROI: {inside_count}", (24, 78))
    if jam_active:
        draw_text(frame, "JAM IN ROI", (24, 116))


def validate_device(device: str) -> str:
    normalized = device.strip().lower()
    if normalized in {"", "auto"}:
        return "0" if torch.cuda.is_available() else "cpu"
    if normalized in {"cpu", "-1"}:
        return "cpu"
    if not torch.cuda.is_available():
        emit({"type": "status", "message": "当前运行环境未启用 CUDA，已自动切换 CPU 推理。", "device": "cpu"})
        return "cpu"
    return device.strip() or "0"


def write_events(path: Path, events: list[FlowEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["frame", "track_id", "event_type", "flow_count", "x", "y", "inside_count"],
        )
        writer.writeheader()
        for event in events:
            writer.writerow(event.__dict__)


def signal_payload(
    event_type: str,
    frame_idx: int,
    flow_count: int,
    inside_count: int,
    stale_seconds: float,
    signal: str,
) -> dict[str, Any]:
    return {
        "type": "jam" if event_type == "jam_detected" else "jam_clear",
        "event_type": event_type,
        "timestamp_ms": int(time.time() * 1000),
        "frame": frame_idx,
        "flow_count": flow_count,
        "inside_count": inside_count,
        "stale_seconds": stale_seconds,
        "signal": signal,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()

    weights = Path(args.weights)
    if not weights.exists():
        raise FileNotFoundError(f"找不到 PT 权重：{weights}")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_path = Path(args.preview_path)
    jam_signal_path = Path(args.jam_signal_path) if args.jam_signal_path else output_dir / "jam_signals.jsonl"
    jam_signal_path.parent.mkdir(parents=True, exist_ok=True)
    jam_signal_path.touch(exist_ok=True)
    roi = parse_point_list(args.roi)
    detect_roi = parse_point_list(args.detect_roi) if args.detect_roi else None
    device = validate_device(args.device)

    cap = source_to_capture(args.source)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频源：{args.source}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output_video = output_dir / "pt_video_flow_monitor.mp4"
    events_csv = output_dir / "flow_events.csv"
    summary_json = output_dir / "flow_summary.json"
    writer = cv2.VideoWriter(str(output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"无法写入结果视频：{output_video}")

    emit({"type": "status", "message": "正在加载 PT 权重", "weights": str(weights), "device": device})
    model = YOLO(str(weights))
    classes = None if args.class_id < 0 else [args.class_id]
    preview_every = max(1, int(round(fps / max(1, args.preview_fps))))
    jam_frames = max(1, int(round(args.jam_seconds * fps)))
    was_inside_roi: dict[int, bool] = {}
    counted_roi: set[int] = set()
    trails: dict[int, deque[tuple[int, int]]] = defaultdict(lambda: deque(maxlen=args.trail))
    events: list[FlowEvent] = []
    flow_count = 0
    last_flow_count = 0
    last_flow_change_frame = 0
    max_inside_count = 0
    jam_active = False
    jam_count = 0
    frame_idx = 0

    emit({"type": "status", "message": "开始 PT 视频检测与流量监测"})
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if args.max_frames > 0 and frame_idx >= args.max_frames:
                break
            frame_idx += 1

            infer_frame, offset = crop_by_roi(frame, detect_roi)
            result = model.track(
                infer_frame,
                persist=True,
                tracker=args.tracker,
                conf=args.conf,
                iou=args.iou,
                imgsz=args.imgsz,
                device=device,
                classes=classes,
                verbose=False,
            )[0]

            annotated = frame.copy()
            boxes = result.boxes
            tracked_count = 0
            inside_count = 0
            if boxes is not None and len(boxes) > 0:
                xyxy = boxes.xyxy.cpu().numpy()
                confs = boxes.conf.cpu().numpy()
                clss = boxes.cls.cpu().numpy().astype(int)
                ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else np.full(len(xyxy), -1, dtype=int)
                names = result.names or {}
                for box, track_id, conf, class_id in zip(xyxy, ids, confs, clss):
                    x1, y1, x2, y2 = box
                    x1 += offset[0]
                    x2 += offset[0]
                    y1 += offset[1]
                    y2 += offset[1]
                    cx, cy = (float(x1 + x2) / 2, float(y1 + y2) / 2)
                    if detect_roi is not None and not point_in_roi((cx, cy), detect_roi):
                        continue

                    inside = point_in_roi((cx, cy), roi)
                    if inside:
                        inside_count += 1

                    if track_id >= 0:
                        tracked_count += 1
                        trails[track_id].append((int(cx), int(cy)))
                        if inside and not was_inside_roi.get(track_id, False) and track_id not in counted_roi:
                            flow_count += 1
                            counted_roi.add(track_id)
                            events.append(FlowEvent(frame_idx, track_id, "roi_enter", flow_count, cx, cy, inside_count))
                        was_inside_roi[track_id] = inside

                    color = (0, 220, 0) if inside else (0, 160, 255)
                    cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                    class_name = str(names.get(int(class_id), class_id))
                    id_text = f"ID {track_id} " if track_id >= 0 else ""
                    draw_text(annotated, f"{id_text}{class_name} {conf:.2f}", (int(x1), max(24, int(y1) - 8)))
                    if track_id >= 0:
                        pts = list(trails[track_id])
                        for p1, p2 in zip(pts, pts[1:]):
                            cv2.line(annotated, p1, p2, (255, 180, 0), 2)

            flow_changed = flow_count != last_flow_count
            if flow_changed:
                last_flow_count = flow_count
                last_flow_change_frame = frame_idx

            stale_frames = frame_idx - last_flow_change_frame
            stale_seconds = stale_frames / fps
            if jam_active and (inside_count == 0 or flow_changed):
                payload = signal_payload("jam_cleared", frame_idx, flow_count, inside_count, stale_seconds, "IO_JAM_OFF")
                write_jsonl(jam_signal_path, payload)
                emit(payload)
                jam_active = False
            if inside_count > 0 and not flow_changed and stale_frames >= jam_frames and not jam_active:
                jam_active = True
                jam_count += 1
                payload = signal_payload("jam_detected", frame_idx, flow_count, inside_count, stale_seconds, "IO_JAM_ON")
                write_jsonl(jam_signal_path, payload)
                emit(payload)

            max_inside_count = max(max_inside_count, inside_count)
            draw_overlay(annotated, roi, detect_roi, flow_count, inside_count, jam_active)
            writer.write(annotated)

            if frame_idx == 1 or frame_idx % preview_every == 0:
                write_image_utf8(preview_path, annotated)
                emit(
                    {
                        "type": "frame",
                        "frame": frame_idx,
                        "preview_path": str(preview_path),
                        "flow_count": flow_count,
                        "inside_count": inside_count,
                        "tracked_count": tracked_count,
                        "jam_active": jam_active,
                    }
                )
    finally:
        cap.release()
        writer.release()

    write_events(events_csv, events)
    summary = {
        "type": "done",
        "frames": frame_idx,
        "flow_count": flow_count,
        "jam_count": jam_count,
        "max_inside_count": max_inside_count,
        "output_video": str(output_video),
        "events_csv": str(events_csv),
        "jam_signals": str(jam_signal_path),
        "summary_json": str(summary_json),
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    emit(summary)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        emit({"type": "error", "message": str(exc)})
        raise
