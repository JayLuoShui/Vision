from __future__ import annotations

import csv
import json
import random
import shutil
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .models import SYNTHETIC_LABEL, JamMode, JamSegment, ProjectState, VideoInfo

ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]


def _ensure_not_cancelled(cancelled: CancelCallback | None) -> None:
    if cancelled and cancelled():
        raise RuntimeError("任务已取消")


def _frame_path(directory: Path, index: int) -> Path:
    return directory / f"{index:06d}.jpg"


def _validate_segment(segment: JamSegment, frame_count: int) -> None:
    values = [
        segment.source_start_frame,
        segment.source_end_frame,
        segment.target_start_frame,
        segment.target_end_frame,
    ]
    if any(value < 0 for value in values):
        raise ValueError("帧编号不能小于 0")
    if segment.source_start_frame > segment.source_end_frame:
        raise ValueError("来源结束帧不能早于来源开始帧")
    if segment.target_start_frame > segment.target_end_frame:
        raise ValueError("目标结束帧不能早于目标开始帧")
    if segment.source_end_frame >= frame_count:
        raise ValueError("堵塞片段超出视频帧范围")
    if segment.mode == JamMode.FULL_FREEZE:
        if segment.source_start_frame != segment.source_end_frame:
            raise ValueError("整帧冻结模式只能选择 1 帧作为冻结帧")
        if segment.target_start_frame != segment.source_start_frame:
            raise ValueError("整帧冻结模式的目标开始帧必须等于冻结帧")
        return
    if segment.target_end_frame >= frame_count:
        raise ValueError("堵塞片段超出视频帧范围")
    if segment.roi is None:
        raise ValueError("ROI 局部冻结模式必须设置 ROI")
    if segment.source_start_frame == segment.target_start_frame and segment.source_end_frame == segment.target_end_frame:
        raise ValueError("来源片段和目标片段不能完全相同")


def calculate_output_frame_count(frame_count: int, segments: list[JamSegment]) -> int:
    total = frame_count
    for segment in segments:
        if segment.enabled and segment.mode == JamMode.FULL_FREEZE:
            total += max(0, segment.target_length() - 1)
    return total


def _validate_roi(roi: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = roi
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("ROI 超出图像范围或宽高无效")
    return x1, y1, x2, y2


def _apply_patch_jitter(
    patch: np.ndarray,
    *,
    rng: random.Random,
    brightness_jitter: bool,
    noise_jitter: bool,
) -> np.ndarray:
    result = patch
    if brightness_jitter:
        beta = rng.randint(-8, 8)
        result = cv2.convertScaleAbs(result, alpha=1.0, beta=beta)
    if noise_jitter:
        noise = rng.normalvariate(0, 1)
        result = np.clip(result.astype(np.int16) + int(round(noise * 3)), 0, 255).astype(np.uint8)
    return result


def _target_roi_with_offset(
    roi: tuple[int, int, int, int],
    width: int,
    height: int,
    *,
    rng: random.Random,
    position_jitter: bool,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = roi
    if not position_jitter:
        return x1, y1, x2, y2
    patch_width = x2 - x1
    patch_height = y2 - y1
    dx = rng.randint(-2, 2)
    dy = rng.randint(-2, 2)
    nx1 = min(max(0, x1 + dx), width - patch_width)
    ny1 = min(max(0, y1 + dy), height - patch_height)
    return nx1, ny1, nx1 + patch_width, ny1 + patch_height


def apply_jam_segments(
    frames_dir: Path,
    synthetic_frames_dir: Path,
    segments: list[JamSegment],
    *,
    frame_count: int,
    brightness_jitter: bool = False,
    noise_jitter: bool = False,
    position_jitter: bool = False,
    seed: int = 1,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> int:
    frames_dir = Path(frames_dir)
    synthetic_frames_dir = Path(synthetic_frames_dir)
    if not frames_dir.exists():
        raise FileNotFoundError(f"抽帧目录不存在：{frames_dir}")
    synthetic_frames_dir.mkdir(parents=True, exist_ok=True)

    enabled_segments = [segment for segment in segments if segment.enabled]
    for segment in enabled_segments:
        _validate_segment(segment, frame_count)

    full_segments = sorted(
        (segment for segment in enabled_segments if segment.mode == JamMode.FULL_FREEZE),
        key=lambda item: item.target_start_frame,
    )
    roi_segments = [segment for segment in enabled_segments if segment.mode == JamMode.ROI_FREEZE]
    output_count = calculate_output_frame_count(frame_count, enabled_segments)
    total_steps = output_count + sum(segment.target_length() for segment in roi_segments)

    output_index = 0
    full_index = 0
    for index in range(frame_count):
        _ensure_not_cancelled(cancelled)
        source = _frame_path(frames_dir, index)
        if not source.exists():
            raise FileNotFoundError(f"缺少帧图片：{source}")
        target = _frame_path(synthetic_frames_dir, output_index)
        shutil.copy2(source, target)
        output_index += 1
        while full_index < len(full_segments) and full_segments[full_index].target_start_frame == index:
            segment = full_segments[full_index]
            for _ in range(segment.target_length() - 1):
                _ensure_not_cancelled(cancelled)
                target = _frame_path(synthetic_frames_dir, output_index)
                shutil.copy2(source, target)
                output_index += 1
            full_index += 1
        if progress:
            progress(output_index, total_steps, "插入冻结帧")

    rng = random.Random(seed)
    for segment in roi_segments:
        for target_index in range(segment.target_start_frame, segment.target_end_frame + 1):
            _ensure_not_cancelled(cancelled)
            offset = (target_index - segment.target_start_frame) % segment.source_length()
            source_index = segment.source_start_frame + offset
            output_target_index = target_index + sum(
                full.target_length() - 1 for full in full_segments if full.target_start_frame < target_index
            )
            source_path = _frame_path(frames_dir, source_index)
            target_path = _frame_path(synthetic_frames_dir, output_target_index)
            target_image = cv2.imread(str(target_path), cv2.IMREAD_COLOR)
            source_image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
            if target_image is None or source_image is None:
                raise RuntimeError("帧图片读取失败")
            height, width = target_image.shape[:2]
            x1, y1, x2, y2 = _validate_roi(segment.roi or (0, 0, 0, 0), width, height)
            patch = source_image[y1:y2, x1:x2].copy()
            patch = _apply_patch_jitter(
                patch,
                rng=rng,
                brightness_jitter=brightness_jitter,
                noise_jitter=noise_jitter,
            )
            tx1, ty1, tx2, ty2 = _target_roi_with_offset(
                (x1, y1, x2, y2),
                width,
                height,
                rng=rng,
                position_jitter=position_jitter,
            )
            target_image[ty1:ty2, tx1:tx2] = patch
            if not cv2.imwrite(str(target_path), target_image):
                raise RuntimeError(f"写入合成帧失败：{target_path}")
            if progress:
                progress(min(total_steps, output_count + target_index + 1), total_steps, "生成 ROI 堵塞帧")
    return output_count


def generate_random_segments(
    *,
    video_info: VideoInfo,
    count: int,
    min_duration_sec: float,
    max_duration_sec: float,
    seed: int,
    mode: JamMode,
    roi: tuple[int, int, int, int] | None = None,
) -> list[JamSegment]:
    if video_info.fps <= 0 or video_info.frame_count <= 0:
        raise ValueError("视频信息无效")
    if count < 0:
        raise ValueError("堵塞段数量不能小于 0")
    if min_duration_sec <= 0 or max_duration_sec < min_duration_sec:
        raise ValueError("堵塞时长设置无效")
    if mode == JamMode.ROI_FREEZE and roi is None:
        raise ValueError("ROI 局部冻结模式必须先绘制 ROI")

    rng = random.Random(seed)
    edge = int(round(2 * video_info.fps))
    valid_start = edge
    valid_end = video_info.frame_count - edge - 1
    if valid_end <= valid_start:
        raise ValueError("视频太短，无法避开前后 2 秒")

    min_frames = max(1, int(round(min_duration_sec * video_info.fps)))
    max_frames = max(min_frames, int(round(max_duration_sec * video_info.fps)))
    if max_frames > valid_end - valid_start + 1:
        raise ValueError("堵塞时长超过可用视频范围")

    intervals: list[tuple[int, int]] = []
    segments: list[JamSegment] = []
    attempts = 0
    max_attempts = max(1000, count * 500)
    while len(segments) < count and attempts < max_attempts:
        attempts += 1
        duration = rng.randint(min_frames, max_frames)
        if mode == JamMode.FULL_FREEZE:
            target_start = rng.randint(valid_start, valid_end)
            target_end = target_start + duration - 1
        else:
            target_start = rng.randint(valid_start, valid_end - duration + 1)
            target_end = target_start + duration - 1
        if any(not (target_end < start or target_start > end) for start, end in intervals):
            continue

        if mode == JamMode.FULL_FREEZE:
            source_start = target_start
            source_end = target_start
        else:
            source_start = rng.randint(0, video_info.frame_count - duration)
            source_end = source_start + duration - 1
            if source_start == target_start and source_end == target_end:
                continue

        segment = JamSegment(
            jam_id=len(segments) + 1,
            mode=mode,
            source_start_frame=source_start,
            source_end_frame=source_end,
            target_start_frame=target_start,
            target_end_frame=target_end,
            roi=roi,
        )
        intervals.append((target_start, target_end))
        segments.append(segment)

    if len(segments) != count:
        raise ValueError("可用视频范围不足，无法生成指定数量的不重叠片段")
    return segments


def export_annotations(output_dir: Path, segments: list[JamSegment], video_info: VideoInfo) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "data_type": SYNTHETIC_LABEL,
        "fps": video_info.fps,
        "width": video_info.width,
        "height": video_info.height,
        "frame_count": video_info.frame_count,
        "segments": [segment.to_dict(video_info.fps) for segment in segments if segment.enabled],
    }
    (output_dir / "jam_segments.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    fields = [
        "jam_id",
        "mode",
        "source_start_time",
        "source_end_time",
        "target_start_time",
        "target_end_time",
        "target_start_frame",
        "target_end_frame",
        "roi",
        "synthetic_label",
    ]
    with (output_dir / "jam_segments.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for segment in segments:
            if not segment.enabled:
                continue
            row = segment.to_dict(video_info.fps)
            row["roi"] = json.dumps(row["roi"], ensure_ascii=False)
            writer.writerow({field: row.get(field, "") for field in fields})


def save_project(path: Path, project: ProjectState) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path: Path) -> ProjectState:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ProjectState.from_dict(data)
