import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO


WINDOWS_CJK_FONT = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc"


@dataclass
class FlowEvent:
    frame: int
    track_id: int
    region_id: str
    region_name: str
    event_type: str
    region_flow_count: int
    x: float
    y: float
    inside_count: int


@dataclass
class FlowRegion:
    id: str
    name: str
    polygon: list[tuple[int, int]]
    count_enabled: bool
    jam_enabled: bool
    jam_seconds: int
    priority: int


@dataclass
class RegionState:
    flow_count: int = 0
    inside_count: int = 0
    max_inside_count: int = 0
    jam_count: int = 0
    counted_ids: set[int] = field(default_factory=set)
    was_inside: dict[int, bool] = field(default_factory=dict)
    last_flow_count: int = 0
    last_flow_change_frame: int = 0
    jam_active: bool = False
    stale_seconds: float = 0.0
    was_occupied: bool = False


@dataclass
class RegionConfig:
    total_count_region: str
    regions: list[FlowRegion]


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
    parser.add_argument("--roi", default=None, help="旧版单 ROI 多边形：x1,y1,x2,y2,x3,y3...")
    parser.add_argument("--regions", default=None, help="多 ROI 配置 JSON 路径")
    parser.add_argument("--detect-roi", default=None, help="只在该区域内检测，格式同 roi")
    parser.add_argument("--conf", type=float, default=0.25, help="检测置信度")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IoU")
    parser.add_argument("--imgsz", type=int, default=960, help="推理输入尺寸")
    parser.add_argument("--device", default="0", help="推理设备，例如 0 或 cpu")
    parser.add_argument("--class-id", type=int, default=-1, help="只检测指定类别；-1 表示全部类别")
    parser.add_argument("--tracker", default="bytetrack.yaml", help="Ultralytics 跟踪器配置")
    parser.add_argument("--preview-fps", type=int, default=30, help="界面预览帧率上限")
    parser.add_argument("--trail", type=int, default=40, help="轨迹显示长度")
    parser.add_argument("--jam-seconds", type=int, default=5, help="旧版单 ROI 堵包秒数")
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


@lru_cache(maxsize=4)
def load_cjk_font(size: int) -> ImageFont.FreeTypeFont:
    if not WINDOWS_CJK_FONT.exists():
        raise FileNotFoundError(f"缺少中文字体：{WINDOWS_CJK_FONT}")
    return ImageFont.truetype(str(WINDOWS_CJK_FONT), size=size)


def draw_text_batch(
    frame: np.ndarray,
    labels: list[tuple[str, tuple[int, int], tuple[int, int, int]]],
) -> None:
    if not labels:
        return
    font_size = 24
    rgb = np.ascontiguousarray(frame[:, :, ::-1])
    image = Image.fromarray(rgb)
    painter = ImageDraw.Draw(image)
    font = load_cjk_font(font_size)
    for text, origin, color in labels:
        painter.text(
            (origin[0], max(0, origin[1] - font_size)),
            text,
            font=font,
            fill=(color[2], color[1], color[0]),
            stroke_width=2,
            stroke_fill=(0, 0, 0),
        )
    frame[:] = np.asarray(image)[:, :, ::-1]


def draw_text(frame: np.ndarray, text: str, origin: tuple[int, int], color: tuple[int, int, int] = (255, 255, 255)) -> None:
    if not text.isascii():
        draw_text_batch(frame, [(text, origin, color)])
        return
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.72, color, 2, cv2.LINE_AA)


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


def validate_polygon_points(value: Any, label: str) -> list[tuple[int, int]]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError(f"{label} 必须至少包含 3 个点")
    points: list[tuple[int, int]] = []
    for index, point in enumerate(value):
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError(f"{label} 第 {index + 1} 个点必须是 [x, y]")
        x, y = point
        if type(x) is not int or type(y) is not int:
            raise ValueError(f"{label} 第 {index + 1} 个点必须是整数坐标")
        points.append((x, y))
    return points


def load_regions(path: str | Path) -> RegionConfig:
    regions_path = Path(path)
    if not regions_path.exists():
        raise FileNotFoundError(f"找不到 regions.json：{regions_path}")
    raw = json.loads(regions_path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("regions.json 顶层必须是对象")
    version = raw.get("version")
    if type(version) is not int or version != 1:
        raise ValueError("regions.json 仅支持 version=1")
    total_count_region = raw.get("total_count_region")
    if not isinstance(total_count_region, str) or not total_count_region.strip():
        raise ValueError("regions.json 缺少有效的 total_count_region")
    total_count_region = total_count_region.strip()
    raw_regions = raw.get("regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise ValueError("regions.json 的 regions 不能为空")

    required_fields = {"id", "name", "polygon", "count_enabled", "jam_enabled", "jam_seconds", "priority"}
    regions: list[FlowRegion] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_regions):
        label = f"regions[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} 必须是对象")
        missing = required_fields - set(item.keys())
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"{label} 缺少字段：{names}")
        region_id = item["id"]
        name = item["name"]
        if not isinstance(region_id, str) or not region_id.strip():
            raise ValueError(f"{label}.id 必须是非空字符串")
        region_id = region_id.strip()
        if region_id in seen_ids:
            raise ValueError(f"regions.json 中存在重复区域 ID：{region_id}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{label}.name 必须是非空字符串")
        name = name.strip()
        polygon = validate_polygon_points(item["polygon"], f"{label}.polygon")
        count_enabled = item["count_enabled"]
        jam_enabled = item["jam_enabled"]
        jam_seconds = item["jam_seconds"]
        priority = item["priority"]
        if not isinstance(count_enabled, bool):
            raise ValueError(f"{label}.count_enabled 必须是布尔值")
        if not isinstance(jam_enabled, bool):
            raise ValueError(f"{label}.jam_enabled 必须是布尔值")
        if type(jam_seconds) is not int or jam_seconds <= 0:
            raise ValueError(f"{label}.jam_seconds 必须是大于 0 的整数")
        if type(priority) is not int:
            raise ValueError(f"{label}.priority 必须是整数")
        seen_ids.add(region_id)
        regions.append(
            FlowRegion(
                id=region_id,
                name=name,
                polygon=polygon,
                count_enabled=count_enabled,
                jam_enabled=jam_enabled,
                jam_seconds=jam_seconds,
                priority=priority,
            )
        )

    if total_count_region not in seen_ids:
        raise ValueError(f"total_count_region 指向不存在的区域：{total_count_region}")
    total_region = next(region for region in regions if region.id == total_count_region)
    if not total_region.count_enabled:
        raise ValueError("total_count_region 对应区域必须开启 count_enabled")
    return RegionConfig(total_count_region=total_count_region, regions=sorted(regions, key=lambda region: region.priority))


def build_single_region_from_legacy_roi(roi_text: str, jam_seconds: int) -> RegionConfig:
    if jam_seconds <= 0:
        raise ValueError("旧版 --jam-seconds 必须大于 0")
    return RegionConfig(
        total_count_region="default",
        regions=[
            FlowRegion(
                id="default",
                name="流量区域",
                polygon=parse_point_list(roi_text),
                count_enabled=True,
                jam_enabled=True,
                jam_seconds=jam_seconds,
                priority=1,
            )
        ],
    )


def resolve_region_config(args: argparse.Namespace) -> RegionConfig:
    if args.regions:
        return load_regions(args.regions)
    if args.roi:
        return build_single_region_from_legacy_roi(args.roi, args.jam_seconds)
    raise ValueError("必须传入 --regions 或 --roi，不能留空")


def write_events(path: Path, events: list[FlowEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "frame",
                "track_id",
                "region_id",
                "region_name",
                "event_type",
                "region_flow_count",
                "x",
                "y",
                "inside_count",
            ],
        )
        writer.writeheader()
        for event in events:
            writer.writerow(event.__dict__)


def signal_payload(
    event_type: str,
    frame_idx: int,
    region: FlowRegion,
    state: RegionState,
    signal: str,
    reason: str = "",
) -> dict[str, Any]:
    payload = {
        "type": "jam",
        "event_type": event_type,
        "timestamp_ms": int(time.time() * 1000),
        "frame": frame_idx,
        "region_id": region.id,
        "region_name": region.name,
        "flow_count": state.flow_count,
        "inside_count": state.inside_count,
        "jam_count": state.jam_count,
        "stale_seconds": round(state.stale_seconds, 3),
        "signal": signal,
    }
    if reason:
        payload["reason"] = reason
    return payload


def region_status(state: RegionState) -> str:
    if state.jam_active:
        return "JAM"
    if state.inside_count <= 0:
        return "IDLE"
    return "RUNNING"


def global_status(states: dict[str, RegionState]) -> str:
    if any(state.jam_active for state in states.values()):
        return "JAM"
    if all(state.inside_count <= 0 for state in states.values()):
        return "IDLE"
    return "RUNNING"


def build_region_payload(region: FlowRegion, state: RegionState) -> dict[str, Any]:
    return {
        "id": region.id,
        "name": region.name,
        "flow_count": state.flow_count,
        "inside_count": state.inside_count,
        "max_inside_count": state.max_inside_count,
        "jam_active": state.jam_active,
        "jam_count": state.jam_count,
        "status": region_status(state),
        "stale_seconds": round(state.stale_seconds, 3),
    }


def draw_regions(
    frame: np.ndarray,
    regions: list[FlowRegion],
    states: dict[str, RegionState],
    detect_roi: list[tuple[int, int]] | None,
) -> None:
    labels: list[tuple[str, tuple[int, int], tuple[int, int, int]]] = []
    if detect_roi is not None:
        cv2.polylines(frame, [np.array(detect_roi, dtype=np.int32)], True, (255, 170, 0), 2)
    for index, region in enumerate(regions):
        state = states[region.id]
        color = (0, 0, 255) if state.jam_active else (0, 210, 255)
        thickness = 4 if state.jam_active else 2
        contour = np.array(region.polygon, dtype=np.int32)
        cv2.polylines(frame, [contour], True, color, thickness)
        min_x = min(point[0] for point in region.polygon)
        min_y = min(point[1] for point in region.polygon)
        label = f"{region.name} | Count: {state.flow_count} | Inside: {state.inside_count} | {region_status(state)}"
        label_y = max(28, min_y - 10)
        text_color = color if state.jam_active else (255, 255, 255)
        labels.append((label, (max(8, min_x), label_y), text_color))
        labels.append((f"{region.name}: {state.flow_count}/{state.inside_count}", (24, 42 + index * 34), text_color))
    draw_text_batch(frame, labels)


def apply_jam_warning_overlay(frame: np.ndarray, frame_idx: int, fps: float, jam_active: bool) -> np.ndarray:
    if not jam_active:
        return frame
    interval_frames = max(1, int(round(fps * 0.5)))
    blink_on = ((frame_idx - 1) // interval_frames) % 2 == 0
    if not blink_on:
        return frame
    red = np.zeros_like(frame)
    red[:, :] = (0, 0, 255)
    frame = cv2.addWeighted(frame, 0.65, red, 0.35, 0)
    draw_text(frame, "JAM WARNING", (24, max(80, 52 + 34)), (0, 0, 255))
    return frame


def is_live_source(source: str) -> bool:
    normalized = source.strip().lower()
    return normalized.isdigit() or normalized.startswith(("rtsp://", "rtmp://", "http://", "https://"))


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
    region_config = resolve_region_config(args)
    detect_roi = parse_point_list(args.detect_roi) if args.detect_roi else None
    device = validate_device(args.device)

    cap = source_to_capture(args.source)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"无法打开视频源：{args.source}")

    output_video = output_dir / "pt_video_flow_monitor.mp4"
    events_csv = output_dir / "flow_events.csv"
    summary_json = output_dir / "flow_summary.json"
    trails: dict[int, deque[tuple[int, int]]] = defaultdict(lambda: deque(maxlen=args.trail))
    region_states = {region.id: RegionState() for region in region_config.regions}
    events: list[FlowEvent] = []
    frame_idx = 0
    writer = None
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(str(output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError(f"无法写入结果视频：{output_video}")

        emit({"type": "status", "message": "正在加载 PT 权重", "weights": str(weights), "device": device})
        model = YOLO(str(weights))
        classes = None if args.class_id < 0 else [args.class_id]
        preview_every = max(1, int(round(fps / max(1, args.preview_fps))))
        emit({"type": "status", "message": "开始 PT 视频检测与流量监测"})
        while True:
            if args.max_frames > 0 and frame_idx >= args.max_frames:
                break
            ok, frame = cap.read()
            if not ok:
                if is_live_source(args.source):
                    raise RuntimeError(f"视频流读取中断：{args.source}")
                break
            frame_idx += 1

            for state in region_states.values():
                state.inside_count = 0

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

                    inside_any = False
                    for region in region_config.regions:
                        state = region_states[region.id]
                        inside = point_in_roi((cx, cy), region.polygon)
                        if inside:
                            inside_any = True
                            state.inside_count += 1
                        if track_id >= 0:
                            was_inside = state.was_inside.get(track_id, False)
                            if region.count_enabled and inside and not was_inside and track_id not in state.counted_ids:
                                state.flow_count += 1
                                state.counted_ids.add(track_id)
                                state.last_flow_change_frame = frame_idx
                                events.append(
                                    FlowEvent(
                                        frame=frame_idx,
                                        track_id=track_id,
                                        region_id=region.id,
                                        region_name=region.name,
                                        event_type="roi_enter",
                                        region_flow_count=state.flow_count,
                                        x=cx,
                                        y=cy,
                                        inside_count=state.inside_count,
                                    )
                                )
                            state.was_inside[track_id] = inside

                    if not inside_any and track_id >= 0:
                        for region in region_config.regions:
                            region_states[region.id].was_inside[track_id] = False

                    if track_id >= 0:
                        tracked_count += 1
                        trails[track_id].append((int(cx), int(cy)))

                    color = (0, 220, 0) if inside_any else (0, 160, 255)
                    cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                    class_name = str(names.get(int(class_id), class_id))
                    id_text = f"ID {track_id} " if track_id >= 0 else ""
                    draw_text(annotated, f"{id_text}{class_name} {conf:.2f}", (int(x1), max(24, int(y1) - 8)))
                    if track_id >= 0:
                        pts = list(trails[track_id])
                        for p1, p2 in zip(pts, pts[1:]):
                            cv2.line(annotated, p1, p2, (255, 180, 0), 2)

            for region in region_config.regions:
                state = region_states[region.id]
                flow_changed = state.flow_count != state.last_flow_count
                became_occupied = state.inside_count > 0 and not state.was_occupied
                if flow_changed or became_occupied:
                    state.last_flow_count = state.flow_count
                    state.last_flow_change_frame = frame_idx
                stale_frames = frame_idx - state.last_flow_change_frame
                state.stale_seconds = stale_frames / fps
                if state.jam_active and (state.inside_count == 0 or flow_changed):
                    payload = signal_payload("jam_cleared", frame_idx, region, state, "IO_JAM_OFF")
                    write_jsonl(jam_signal_path, payload)
                    emit(payload)
                    state.jam_active = False
                jam_frames = max(1, int(round(region.jam_seconds * fps)))
                if region.jam_enabled and state.inside_count > 0 and not flow_changed and stale_frames >= jam_frames and not state.jam_active:
                    state.jam_active = True
                    state.jam_count += 1
                    payload = signal_payload("jam_detected", frame_idx, region, state, "IO_JAM_ON")
                    write_jsonl(jam_signal_path, payload)
                    emit(payload)
                state.max_inside_count = max(state.max_inside_count, state.inside_count)
                state.was_occupied = state.inside_count > 0

            total_state = region_states[region_config.total_count_region]
            global_jam_active = any(state.jam_active for state in region_states.values())
            draw_regions(annotated, region_config.regions, region_states, detect_roi)
            annotated = apply_jam_warning_overlay(annotated, frame_idx, fps, global_jam_active)
            writer.write(annotated)

            if frame_idx == 1 or frame_idx % preview_every == 0:
                write_image_utf8(preview_path, annotated)
                emit(
                    {
                        "type": "frame",
                        "frame": frame_idx,
                        "preview_path": str(preview_path),
                        "total_count": total_state.flow_count,
                        "flow_count": total_state.flow_count,
                        "inside_count": total_state.inside_count,
                        "tracked_count": tracked_count,
                        "jam_active": global_jam_active,
                        "global_status": global_status(region_states),
                        "regions": [build_region_payload(region, region_states[region.id]) for region in region_config.regions],
                    }
                )
    finally:
        for region in region_config.regions:
            state = region_states[region.id]
            if state.jam_active:
                state.inside_count = 0
                payload = signal_payload(
                    "jam_cleared",
                    frame_idx,
                    region,
                    state,
                    "IO_JAM_OFF",
                    reason="monitor_stopped",
                )
                write_jsonl(jam_signal_path, payload)
                emit(payload)
                state.jam_active = False
        cap.release()
        if writer is not None:
            writer.release()

    write_events(events_csv, events)
    total_state = region_states[region_config.total_count_region]
    global_jam_count = sum(state.jam_count for state in region_states.values())
    summary = {
        "type": "done",
        "frames": frame_idx,
        "total_count_region": region_config.total_count_region,
        "total_count": total_state.flow_count,
        "flow_count": total_state.flow_count,
        "jam_count": global_jam_count,
        "global_jam_count": global_jam_count,
        "max_inside_count": total_state.max_inside_count,
        "regions": [build_region_payload(region, region_states[region.id]) for region in region_config.regions],
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
