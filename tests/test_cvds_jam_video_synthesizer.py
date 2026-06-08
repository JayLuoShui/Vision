import csv
import json
from pathlib import Path

import cv2
import numpy as np

from cvds_jam_video_synthesizer.core import (
    apply_jam_segments,
    export_annotations,
    generate_random_segments,
    load_project,
    save_project,
)
from cvds_jam_video_synthesizer.models import JamMode, JamSegment, ProjectState, VideoInfo


def _write_frame(path: Path, value: int, size: tuple[int, int] = (6, 4)) -> None:
    image = np.full((size[1], size[0], 3), value, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def _read_frame(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def test_generate_random_segments_are_non_overlapping_and_avoid_edges() -> None:
    video = VideoInfo(fps=10.0, width=640, height=360, frame_count=500)

    segments = generate_random_segments(
        video_info=video,
        count=5,
        min_duration_sec=1.0,
        max_duration_sec=2.0,
        seed=20260601,
        mode=JamMode.ROI_FREEZE,
        roi=(10, 20, 100, 120),
    )

    assert len(segments) == 5
    intervals = sorted((segment.target_start_frame, segment.target_end_frame) for segment in segments)
    for start, end in intervals:
        assert start >= 20
        assert end <= 479
    for previous, current in zip(intervals, intervals[1:]):
        assert previous[1] < current[0]
    for segment in segments:
        assert segment.source_start_frame != segment.target_start_frame
        assert segment.mode == JamMode.ROI_FREEZE
        assert segment.roi == (10, 20, 100, 120)


def test_full_frame_freeze_inserts_repeated_frame_before_following_frames(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    out_dir = tmp_path / "synthetic_frames"
    frames_dir.mkdir()
    for index in range(6):
        _write_frame(frames_dir / f"{index:06d}.jpg", index * 30)

    segment = JamSegment(
        jam_id=1,
        mode=JamMode.FULL_FREEZE,
        source_start_frame=2,
        source_end_frame=2,
        target_start_frame=2,
        target_end_frame=4,
    )

    output_count = apply_jam_segments(frames_dir, out_dir, [segment], frame_count=6)

    assert output_count == 8
    assert int(_read_frame(out_dir / "000000.jpg")[0, 0, 0]) == 0
    assert int(_read_frame(out_dir / "000001.jpg")[0, 0, 0]) == 30
    assert int(_read_frame(out_dir / "000004.jpg")[0, 0, 0]) == 60
    assert int(_read_frame(out_dir / "000005.jpg")[0, 0, 0]) == 90
    assert int(_read_frame(out_dir / "000007.jpg")[0, 0, 0]) == 150


def test_random_full_frame_segments_use_single_freeze_frame() -> None:
    video = VideoInfo(fps=10.0, width=640, height=360, frame_count=500)

    segments = generate_random_segments(
        video_info=video,
        count=3,
        min_duration_sec=10.0,
        max_duration_sec=20.0,
        seed=20260602,
        mode=JamMode.FULL_FREEZE,
    )

    assert len(segments) == 3
    for segment in segments:
        assert segment.source_start_frame == segment.source_end_frame
        assert segment.target_start_frame >= 20
        assert segment.target_length() >= 100
        assert segment.target_length() <= 200


def test_roi_freeze_replaces_only_roi_area(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    out_dir = tmp_path / "synthetic_frames"
    frames_dir.mkdir()
    for index in range(4):
        _write_frame(frames_dir / f"{index:06d}.jpg", 20 + index * 40)

    segment = JamSegment(
        jam_id=1,
        mode=JamMode.ROI_FREEZE,
        source_start_frame=0,
        source_end_frame=0,
        target_start_frame=2,
        target_end_frame=2,
        roi=(1, 1, 4, 3),
    )

    apply_jam_segments(frames_dir, out_dir, [segment], frame_count=4)

    image = _read_frame(out_dir / "000002.jpg")
    assert abs(int(image[0, 0, 0]) - 100) <= 3
    assert abs(int(image[1, 1, 0]) - 20) <= 3
    assert abs(int(image[2, 3, 0]) - 20) <= 3


def test_annotation_export_marks_synthetic_outputs(tmp_path: Path) -> None:
    video = VideoInfo(fps=10.0, width=640, height=360, frame_count=200)
    segment = JamSegment(
        jam_id=7,
        mode=JamMode.ROI_FREEZE,
        source_start_frame=10,
        source_end_frame=20,
        target_start_frame=50,
        target_end_frame=70,
        roi=(1, 2, 3, 4),
    )

    export_annotations(tmp_path, [segment], video)

    payload = json.loads((tmp_path / "jam_segments.json").read_text(encoding="utf-8"))
    assert payload["data_type"] == "synthetic/simulated"
    assert payload["segments"][0]["source_start_time"] == 1.0
    assert payload["segments"][0]["target_end_time"] == 7.0

    with (tmp_path / "jam_segments.csv").open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["synthetic_label"] == "synthetic/simulated"
    assert rows[0]["roi"] == "[1, 2, 3, 4]"


def test_project_save_and_load_roundtrip(tmp_path: Path) -> None:
    project = ProjectState(
        video_path="D:/input/demo.mp4",
        project_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
        extracted=True,
        roi=(10, 20, 30, 40),
        random_seed=99,
        random_count=2,
        random_min_duration=1.5,
        random_max_duration=3.0,
        brightness_jitter=True,
        noise_jitter=True,
        position_jitter=True,
        segments=[
            JamSegment(
                jam_id=1,
                mode=JamMode.FULL_FREEZE,
                source_start_frame=1,
                source_end_frame=3,
                target_start_frame=10,
                target_end_frame=12,
            )
        ],
    )

    path = tmp_path / "project.json"
    save_project(path, project)
    loaded = load_project(path)

    assert loaded == project
