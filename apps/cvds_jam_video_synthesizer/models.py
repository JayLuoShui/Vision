from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


SYNTHETIC_LABEL = "synthetic/simulated"


class JamMode(StrEnum):
    FULL_FREEZE = "full_freeze"
    ROI_FREEZE = "roi_freeze"


@dataclass(frozen=True)
class VideoInfo:
    fps: float
    width: int
    height: int
    frame_count: int

    @property
    def duration_sec(self) -> float:
        if self.fps <= 0:
            return 0.0
        return self.frame_count / self.fps


@dataclass(frozen=True)
class JamSegment:
    jam_id: int
    mode: JamMode
    source_start_frame: int
    source_end_frame: int
    target_start_frame: int
    target_end_frame: int
    roi: tuple[int, int, int, int] | None = None
    enabled: bool = True

    def source_length(self) -> int:
        return self.source_end_frame - self.source_start_frame + 1

    def target_length(self) -> int:
        return self.target_end_frame - self.target_start_frame + 1

    def to_dict(self, fps: float | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jam_id": self.jam_id,
            "mode": self.mode.value,
            "source_start_frame": self.source_start_frame,
            "source_end_frame": self.source_end_frame,
            "target_start_frame": self.target_start_frame,
            "target_end_frame": self.target_end_frame,
            "roi": list(self.roi) if self.roi else None,
            "enabled": self.enabled,
            "synthetic_label": SYNTHETIC_LABEL,
        }
        if fps and fps > 0:
            payload.update(
                {
                    "source_start_time": round(self.source_start_frame / fps, 6),
                    "source_end_time": round(self.source_end_frame / fps, 6),
                    "target_start_time": round(self.target_start_frame / fps, 6),
                    "target_end_time": round(self.target_end_frame / fps, 6),
                }
            )
        return payload

    @staticmethod
    def from_dict(data: dict[str, Any], fps: float | None = None) -> "JamSegment":
        def frame_value(frame_key: str, time_key: str) -> int:
            if frame_key in data and data[frame_key] is not None:
                return int(data[frame_key])
            if fps and fps > 0 and time_key in data:
                return int(round(float(data[time_key]) * fps))
            raise ValueError(f"缺少字段：{frame_key}")

        roi_data = data.get("roi")
        roi = tuple(int(value) for value in roi_data) if roi_data else None
        if roi is not None and len(roi) != 4:
            raise ValueError("ROI 必须是 4 个整数")
        return JamSegment(
            jam_id=int(data["jam_id"]),
            mode=JamMode(data["mode"]),
            source_start_frame=frame_value("source_start_frame", "source_start_time"),
            source_end_frame=frame_value("source_end_frame", "source_end_time"),
            target_start_frame=frame_value("target_start_frame", "target_start_time"),
            target_end_frame=frame_value("target_end_frame", "target_end_time"),
            roi=roi,
            enabled=bool(data.get("enabled", True)),
        )


@dataclass(frozen=True)
class ProjectState:
    video_path: str = ""
    project_dir: str = ""
    output_dir: str = ""
    extracted: bool = False
    roi: tuple[int, int, int, int] | None = None
    random_seed: int = 1
    random_count: int = 3
    random_min_duration: float = 2.0
    random_max_duration: float = 5.0
    brightness_jitter: bool = False
    noise_jitter: bool = False
    position_jitter: bool = False
    segments: list[JamSegment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "app": "CVDS 包裹堵塞视频合成工具",
            "data_type": SYNTHETIC_LABEL,
            "video_path": self.video_path,
            "project_dir": self.project_dir,
            "output_dir": self.output_dir,
            "extracted": self.extracted,
            "roi": list(self.roi) if self.roi else None,
            "random_seed": self.random_seed,
            "random_count": self.random_count,
            "random_min_duration": self.random_min_duration,
            "random_max_duration": self.random_max_duration,
            "brightness_jitter": self.brightness_jitter,
            "noise_jitter": self.noise_jitter,
            "position_jitter": self.position_jitter,
            "segments": [segment.to_dict() for segment in self.segments],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ProjectState":
        roi_data = data.get("roi")
        roi = tuple(int(value) for value in roi_data) if roi_data else None
        return ProjectState(
            video_path=str(data.get("video_path", "")),
            project_dir=str(data.get("project_dir", "")),
            output_dir=str(data.get("output_dir", "")),
            extracted=bool(data.get("extracted", False)),
            roi=roi,
            random_seed=int(data.get("random_seed", 1)),
            random_count=int(data.get("random_count", 3)),
            random_min_duration=float(data.get("random_min_duration", 2.0)),
            random_max_duration=float(data.get("random_max_duration", 5.0)),
            brightness_jitter=bool(data.get("brightness_jitter", False)),
            noise_jitter=bool(data.get("noise_jitter", False)),
            position_jitter=bool(data.get("position_jitter", False)),
            segments=[JamSegment.from_dict(item) for item in data.get("segments", [])],
        )
