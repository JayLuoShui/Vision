from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

import cv2

from .models import VideoInfo

ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]


def read_video_info(video_path: Path) -> VideoInfo:
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise RuntimeError("视频无法打开，请检查文件格式或路径")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or width <= 0 or height <= 0 or frame_count <= 0:
            raise RuntimeError("视频信息读取失败")
        return VideoInfo(fps=fps, width=width, height=height, frame_count=frame_count)
    finally:
        capture.release()


def extract_frames(
    video_path: Path,
    frames_dir: Path,
    *,
    every_n_per_second: int | None = None,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> int:
    info = read_video_info(video_path)
    capture = cv2.VideoCapture(str(video_path))
    frames_dir.mkdir(parents=True, exist_ok=True)
    step = 1
    if every_n_per_second:
        if every_n_per_second <= 0:
            raise ValueError("每秒抽帧数量必须大于 0")
        step = max(1, int(round(info.fps / every_n_per_second)))

    written = 0
    frame_index = 0
    try:
        while True:
            if cancelled and cancelled():
                raise RuntimeError("任务已取消")
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % step == 0:
                target = frames_dir / f"{written:06d}.jpg"
                if not cv2.imwrite(str(target), frame):
                    raise RuntimeError(f"写入帧失败：{target}")
                written += 1
            frame_index += 1
            if progress:
                progress(frame_index, info.frame_count, "抽帧")
    finally:
        capture.release()
    return written


def encode_video_opencv(
    frames_dir: Path,
    output_path: Path,
    *,
    fps: float,
    width: int,
    height: int,
    frame_count: int,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("视频编码器打开失败")
    try:
        for index in range(frame_count):
            if cancelled and cancelled():
                raise RuntimeError("任务已取消")
            frame_path = frames_dir / f"{index:06d}.jpg"
            frame = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
            if frame is None:
                raise RuntimeError(f"读取合成帧失败：{frame_path}")
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            writer.write(frame)
            if progress:
                progress(index + 1, frame_count, "编码视频")
    finally:
        writer.release()


def encode_video_ffmpeg(
    frames_dir: Path,
    output_path: Path,
    *,
    fps: float,
    ffmpeg_path: Path,
) -> None:
    if not ffmpeg_path.exists():
        raise FileNotFoundError(f"找不到 ffmpeg.exe：{ffmpeg_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(ffmpeg_path),
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "%06d.jpg"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "FFmpeg 编码失败")
