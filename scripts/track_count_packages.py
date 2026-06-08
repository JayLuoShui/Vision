import argparse
import csv
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = ROOT / "weights" / "cvds_yolo26n_package_best.pt"


@dataclass
class CountEvent:
    frame: int
    track_id: int
    event_type: str
    count: int
    x: float
    y: float
    direction: str


def parse_point_list(text: str) -> list[tuple[int, int]]:
    values = [int(float(x.strip())) for x in text.split(",") if x.strip()]
    if len(values) < 4 or len(values) % 2 != 0:
        raise ValueError("坐标必须是 x1,y1,x2,y2 或多边形点列表")
    return [(values[i], values[i + 1]) for i in range(0, len(values), 2)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="交叉带移动包裹检测、跟踪与计数")
    parser.add_argument("--source", required=True, help="视频文件、图片目录、RTSP 地址或摄像头编号")
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS), help="训练好的 YOLO26n 权重")
    parser.add_argument("--output", default=str(ROOT / "runs" / "package_count" / "output.mp4"), help="结果视频输出路径")
    parser.add_argument("--events", default=None, help="计数事件 CSV；不填则与 output 同名")
    parser.add_argument("--line", default=None, help="过线计数线：x1,y1,x2,y2")
    parser.add_argument("--roi", default=None, help="ROI 进入计数多边形：x1,y1,x2,y2,x3,y3...")
    parser.add_argument("--detect-roi", default=None, help="只在该区域内检测，再映射回原图：x1,y1,x2,y2 或多边形点列表")
    parser.add_argument("--direction", choices=["both", "positive", "negative"], default="both", help="过线方向")
    parser.add_argument("--conf", type=float, default=0.35, help="检测置信度")
    parser.add_argument("--iou", type=float, default=0.5, help="NMS IoU")
    parser.add_argument("--imgsz", type=int, default=960, help="推理输入尺寸")
    parser.add_argument("--device", default="0", help="推理设备，例如 cpu 或 0")
    parser.add_argument("--tracker", default="bytetrack.yaml", help="Ultralytics 跟踪器配置")
    parser.add_argument("--trail", type=int, default=40, help="轨迹显示长度")
    parser.add_argument("--show", action="store_true", help="实时显示窗口")
    return parser.parse_args()


def side_of_line(point: tuple[float, float], a: tuple[int, int], b: tuple[int, int]) -> float:
    return (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])


def direction_allowed(prev_side: float, curr_side: float, direction: str) -> bool:
    if prev_side == 0 or curr_side == 0:
        return False
    if prev_side * curr_side > 0:
        return False
    if direction == "both":
        return True
    if direction == "positive":
        return prev_side < 0 < curr_side
    return prev_side > 0 > curr_side


def point_in_roi(point: tuple[float, float], polygon: list[tuple[int, int]]) -> bool:
    contour = np.array(polygon, dtype=np.int32)
    return cv2.pointPolygonTest(contour, point, False) >= 0


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


def source_to_capture(source: str) -> cv2.VideoCapture:
    if source.isdigit():
        return cv2.VideoCapture(int(source))
    return cv2.VideoCapture(source)


def draw_text(frame: np.ndarray, text: str, origin: tuple[int, int]) -> None:
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)


def write_events(path: Path, events: list[CountEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "track_id", "event_type", "count", "x", "y", "direction"])
        writer.writeheader()
        for event in events:
            writer.writerow(event.__dict__)


def main() -> None:
    args = parse_args()
    weights = Path(args.weights)
    if not weights.exists():
        raise FileNotFoundError(f"找不到权重文件：{weights}")
    if not args.line and not args.roi:
        raise ValueError("必须提供 --line 或 --roi，明确计数位置")

    line = parse_point_list(args.line) if args.line else None
    if line and len(line) != 2:
        raise ValueError("--line 必须是 2 个点")
    roi = parse_point_list(args.roi) if args.roi else None
    if roi and len(roi) < 3:
        raise ValueError("--roi 至少需要 3 个点")
    detect_roi = parse_point_list(args.detect_roi) if args.detect_roi else None

    cap = source_to_capture(args.source)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频源：{args.source}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"无法写入结果视频：{output}")

    model = YOLO(str(weights))
    prev_line_side: dict[int, float] = {}
    was_inside_roi: dict[int, bool] = {}
    counted_line: set[int] = set()
    counted_roi: set[int] = set()
    trails: dict[int, deque] = defaultdict(lambda: deque(maxlen=args.trail))
    events: list[CountEvent] = []
    count = 0
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        infer_frame, offset, detect_roi_rect = crop_by_roi(frame, detect_roi)
        result = model.track(
            infer_frame,
            persist=True,
            tracker=args.tracker,
            conf=args.conf,
            iou=args.iou,
            imgsz=args.imgsz,
            device=args.device,
            verbose=False,
        )[0]

        annotated = frame.copy()
        boxes = result.boxes
        if boxes is not None and boxes.id is not None:
            xyxy = boxes.xyxy.cpu().numpy()
            ids = boxes.id.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy()
            for box, track_id, conf in zip(xyxy, ids, confs):
                x1, y1, x2, y2 = box
                x1 += offset[0]
                x2 += offset[0]
                y1 += offset[1]
                y2 += offset[1]
                cx, cy = (float(x1 + x2) / 2, float(y1 + y2) / 2)
                trails[track_id].append((int(cx), int(cy)))

                if line:
                    curr = side_of_line((cx, cy), line[0], line[1])
                    prev = prev_line_side.get(track_id)
                    if prev is not None and track_id not in counted_line and direction_allowed(prev, curr, args.direction):
                        count += 1
                        counted_line.add(track_id)
                        direction = "positive" if prev < curr else "negative"
                        events.append(CountEvent(frame_idx, track_id, "line_cross", count, cx, cy, direction))
                    prev_line_side[track_id] = curr

                if roi:
                    inside = point_in_roi((cx, cy), roi)
                    if inside and not was_inside_roi.get(track_id, False) and track_id not in counted_roi:
                        count += 1
                        counted_roi.add(track_id)
                        events.append(CountEvent(frame_idx, track_id, "roi_enter", count, cx, cy, "enter"))
                    was_inside_roi[track_id] = inside

                cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 220, 0), 2)
                draw_text(annotated, f"ID {track_id} parcel {conf:.2f}", (int(x1), max(22, int(y1) - 8)))
                pts = list(trails[track_id])
                for p1, p2 in zip(pts, pts[1:]):
                    cv2.line(annotated, p1, p2, (255, 180, 0), 2)

        if line:
            cv2.line(annotated, line[0], line[1], (0, 0, 255), 3)
        if roi:
            cv2.polylines(annotated, [np.array(roi, dtype=np.int32)], True, (0, 0, 255), 3)
        if detect_roi_rect:
            x1, y1, x2, y2 = detect_roi_rect
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 160, 0), 2)
        draw_text(annotated, f"COUNT: {count}", (24, 42))
        writer.write(annotated)
        if args.show:
            cv2.imshow("CVDS package tracking count", annotated)
            if cv2.waitKey(1) & 0xFF == 27:
                break

    cap.release()
    writer.release()
    if args.show:
        cv2.destroyAllWindows()

    events_path = Path(args.events) if args.events else output.with_suffix(".events.csv")
    write_events(events_path, events)
    summary = {"output": str(output), "events": str(events_path), "count": count, "frames": frame_idx}
    output.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
